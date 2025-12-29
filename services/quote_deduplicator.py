"""
Quote deduplication service.

Identifies and merges similar quotes within the same language (EN vs EN, RU vs RU),
while preserving bilingual relationships.
"""

import re
from typing import List, Tuple, Optional, Dict, Set
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Quote, QuoteTranslation
from logger_config import logger


class QuoteDeduplicator:
    """Service for deduplicating similar quotes."""
    
    def __init__(
        self,
        db: Session,
        token_threshold: float = 0.80,
        fuzzy_threshold: float = 0.90,
        min_length_for_fuzzy: int = 20
    ):
        """
        Initialize deduplicator.
        
        Args:
            db: Database session
            token_threshold: Minimum token overlap ratio to consider duplicates (0.0-1.0)
            fuzzy_threshold: Minimum fuzzy match ratio to consider duplicates (0.0-1.0)
            min_length_for_fuzzy: Minimum text length to use fuzzy matching
        """
        self.db = db
        self.token_threshold = token_threshold
        self.fuzzy_threshold = fuzzy_threshold
        self.min_length_for_fuzzy = min_length_for_fuzzy
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for comparison.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text (lowercase, trimmed, extra whitespace removed)
        """
        # Remove extra whitespace and normalize
        normalized = ' '.join(text.strip().split())
        return normalized.lower()
    
    @staticmethod
    def tokenize_text(text: str) -> Set[str]:
        """
        Tokenize text into a set of lowercase words.
        
        Args:
            text: Input text
            
        Returns:
            Set of unique lowercase words
        """
        tokens = re.findall(r'\b\w+\b', text.lower())
        return set(tokens)
    
    def calculate_exact_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate exact match similarity (normalized text comparison).
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            1.0 if exact match, 0.0 otherwise
        """
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        return 1.0 if norm1 == norm2 else 0.0
    
    def calculate_token_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate token overlap similarity (Jaccard similarity).
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity ratio (0.0-1.0)
        """
        tokens1 = self.tokenize_text(text1)
        tokens2 = self.tokenize_text(text2)
        
        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_fuzzy_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate fuzzy string similarity using SequenceMatcher.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity ratio (0.0-1.0)
        """
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def calculate_similarity(
        self,
        quote1: Quote,
        quote2: Quote
    ) -> Tuple[float, str]:
        """
        Calculate similarity between two quotes using multiple methods.
        
        Args:
            quote1: First quote
            quote2: Second quote
            
        Returns:
            Tuple of (similarity_score, method_used)
        """
        text1 = quote1.text
        text2 = quote2.text
        
        # Method 1: Exact match
        exact_score = self.calculate_exact_similarity(text1, text2)
        if exact_score == 1.0:
            return 1.0, 'exact'
        
        # Method 2: Token overlap
        token_score = self.calculate_token_similarity(text1, text2)
        if token_score >= self.token_threshold:
            return token_score, 'token'
        
        # Method 3: Fuzzy matching (only for longer texts)
        min_len = min(len(text1), len(text2))
        if min_len >= self.min_length_for_fuzzy:
            fuzzy_score = self.calculate_fuzzy_similarity(text1, text2)
            if fuzzy_score >= self.fuzzy_threshold:
                return fuzzy_score, 'fuzzy'
        
        # Return best score found
        return max(exact_score, token_score), 'token' if token_score > 0 else 'none'
    
    def are_similar(
        self,
        quote1: Quote,
        quote2: Quote
    ) -> Tuple[bool, float, str]:
        """
        Check if two quotes are similar enough to be considered duplicates.
        
        Args:
            quote1: First quote
            quote2: Second quote
            
        Returns:
            Tuple of (is_similar, similarity_score, method)
        """
        # Never compare quotes of different languages
        if quote1.language != quote2.language:
            return False, 0.0, 'different_language'
        
        # Never merge quotes in the same bilingual_group_id (they're translations)
        if (quote1.bilingual_group_id and quote2.bilingual_group_id and
            quote1.bilingual_group_id == quote2.bilingual_group_id):
            return False, 0.0, 'same_bilingual_group'
        
        score, method = self.calculate_similarity(quote1, quote2)
        
        # Determine if similar based on method
        is_similar = False
        if method == 'exact':
            is_similar = True
        elif method == 'token' and score >= self.token_threshold:
            is_similar = True
        elif method == 'fuzzy' and score >= self.fuzzy_threshold:
            is_similar = True
        
        return is_similar, score, method
    
    def select_quote_to_keep(self, quotes: List[Quote]) -> Quote:
        """
        Select which quote to keep based on metadata priority.
        
        Priority: bilingual_group_id > author_id > source_id > created_at > id
        
        Args:
            quotes: List of duplicate quotes
            
        Returns:
            Quote to keep
        """
        if not quotes:
            raise ValueError("Cannot select from empty list")
        
        if len(quotes) == 1:
            return quotes[0]
        
        # Score each quote based on metadata
        def score_quote(quote: Quote) -> Tuple[int, int, int, Optional[int], int]:
            return (
                1 if quote.bilingual_group_id else 0,  # Has bilingual_group_id
                1 if quote.author_id else 0,  # Has author_id
                1 if quote.source_id else 0,  # Has source_id
                quote.created_at.timestamp() if quote.created_at else 0,  # Created_at timestamp
                -quote.id  # Lower ID is better (negate for descending sort)
            )
        
        # Sort by score (highest first)
        sorted_quotes = sorted(quotes, key=score_quote, reverse=True)
        return sorted_quotes[0]
    
    def merge_bilingual_groups(
        self,
        kept_quote: Quote,
        removed_quote: Quote
    ) -> None:
        """
        Merge bilingual groups when quotes are merged.
        
        Args:
            kept_quote: Quote being kept
            removed_quote: Quote being removed
        """
        kept_group_id = kept_quote.bilingual_group_id
        removed_group_id = removed_quote.bilingual_group_id
        
        # If kept quote has a group, use it
        if kept_group_id:
            target_group_id = kept_group_id
        # If removed quote has a group but kept doesn't, transfer it
        elif removed_group_id:
            target_group_id = removed_group_id
            kept_quote.bilingual_group_id = target_group_id
            self.db.commit()
            return
        else:
            # Neither has a group, nothing to merge
            return
        
        # If both have different groups, merge removed group into kept group
        if removed_group_id and removed_group_id != kept_group_id:
            # Update all quotes in removed group to use kept group
            self.db.query(Quote).filter(
                Quote.bilingual_group_id == removed_group_id
            ).update({
                Quote.bilingual_group_id: target_group_id
            })
            self.db.commit()
            logger.debug(
                f"Merged bilingual_group_id {removed_group_id} into {target_group_id}"
            )
    
    def update_translation_links(
        self,
        kept_quote: Quote,
        removed_quote: Quote
    ) -> int:
        """
        Update QuoteTranslation links when merging quotes.
        
        Args:
            kept_quote: Quote being kept
            removed_quote: Quote being removed
            
        Returns:
            Number of translation links updated
        """
        updated_count = 0
        
        # Update links where removed quote is the source
        links_from_removed = self.db.query(QuoteTranslation).filter(
            QuoteTranslation.quote_id == removed_quote.id
        ).all()
        
        for link in links_from_removed:
            # Check if link already exists for kept quote
            existing = self.db.query(QuoteTranslation).filter(
                QuoteTranslation.quote_id == kept_quote.id,
                QuoteTranslation.translated_quote_id == link.translated_quote_id
            ).first()
            
            if existing:
                # Link already exists, just delete the duplicate
                self.db.delete(link)
            else:
                # Update link to point to kept quote
                link.quote_id = kept_quote.id
            updated_count += 1
        
        # Update links where removed quote is the target
        links_to_removed = self.db.query(QuoteTranslation).filter(
            QuoteTranslation.translated_quote_id == removed_quote.id
        ).all()
        
        for link in links_to_removed:
            # Check if link already exists for kept quote
            existing = self.db.query(QuoteTranslation).filter(
                QuoteTranslation.quote_id == link.quote_id,
                QuoteTranslation.translated_quote_id == kept_quote.id
            ).first()
            
            if existing:
                # Link already exists, just delete the duplicate
                self.db.delete(link)
            else:
                # Update link to point to kept quote
                link.translated_quote_id = kept_quote.id
            updated_count += 1
        
        self.db.commit()
        return updated_count
    
    def preserve_metadata(
        self,
        kept_quote: Quote,
        removed_quote: Quote
    ) -> None:
        """
        Preserve metadata from removed quote if kept quote doesn't have it.
        
        Args:
            kept_quote: Quote being kept
            removed_quote: Quote being removed
        """
        updated = False
        
        # Preserve author_id
        if not kept_quote.author_id and removed_quote.author_id:
            kept_quote.author_id = removed_quote.author_id
            updated = True
        
        # Preserve source_id
        if not kept_quote.source_id and removed_quote.source_id:
            kept_quote.source_id = removed_quote.source_id
            updated = True
        
        if updated:
            self.db.commit()
    
    def merge_quotes(
        self,
        quotes: List[Quote],
        dry_run: bool = False
    ) -> Dict:
        """
        Merge duplicate quotes intelligently.
        
        Args:
            quotes: List of duplicate quotes to merge
            dry_run: If True, only report what would be done
            
        Returns:
            Dictionary with merge statistics
        """
        if len(quotes) < 2:
            return {'merged': 0, 'removed': 0, 'links_updated': 0}
        
        # Select quote to keep
        kept_quote = self.select_quote_to_keep(quotes)
        removed_quotes = [q for q in quotes if q.id != kept_quote.id]
        
        stats = {
            'merged': 1,
            'removed': len(removed_quotes),
            'links_updated': 0,
            'groups_merged': 0
        }
        
        if dry_run:
            logger.info(
                f"Would merge {len(removed_quotes)} quotes into quote ID {kept_quote.id}"
            )
            return stats
        
        # Process each removed quote
        for removed_quote in removed_quotes:
            # Merge bilingual groups
            old_group = removed_quote.bilingual_group_id
            self.merge_bilingual_groups(kept_quote, removed_quote)
            if old_group and old_group != kept_quote.bilingual_group_id:
                stats['groups_merged'] += 1
            
            # Update translation links
            links_updated = self.update_translation_links(kept_quote, removed_quote)
            stats['links_updated'] += links_updated
            
            # Preserve metadata
            self.preserve_metadata(kept_quote, removed_quote)
            
            # Delete removed quote
            self.db.delete(removed_quote)
        
        self.db.commit()
        logger.debug(
            f"Merged {len(removed_quotes)} quotes into quote ID {kept_quote.id}"
        )
        
        return stats
    
    def find_similar_quotes(
        self,
        language: str,
        limit: Optional[int] = None
    ) -> List[Tuple[Quote, Quote, float, str]]:
        """
        Find similar quotes within the same language.
        
        Uses optimized approach:
        1. Exact matches via hash lookup (O(n))
        2. Token-based candidate filtering to reduce comparisons
        3. Fuzzy matching only on promising candidates
        
        Args:
            language: Language code ('en' or 'ru')
            limit: Optional limit on number of quotes to process
            
        Returns:
            List of tuples (quote1, quote2, similarity_score, method)
        """
        # Get all quotes of the specified language
        query = self.db.query(Quote).filter(Quote.language == language)
        
        if limit:
            query = query.limit(limit)
        
        quotes = query.all()
        total_quotes = len(quotes)
        similar_pairs = []
        
        logger.info(f"Checking {total_quotes} {language.upper()} quotes for similarities...")
        logger.info("Using optimized similarity detection...")
        
        # Step 1: Find exact duplicates using hash lookup (O(n))
        exact_matches = {}
        normalized_to_quotes = {}
        
        for quote in quotes:
            normalized = self.normalize_text(quote.text)
            if normalized not in normalized_to_quotes:
                normalized_to_quotes[normalized] = []
            normalized_to_quotes[normalized].append(quote)
        
        # Add exact matches
        for normalized, quote_list in normalized_to_quotes.items():
            if len(quote_list) > 1:
                # All quotes with same normalized text are exact matches
                for i, q1 in enumerate(quote_list):
                    for q2 in quote_list[i + 1:]:
                        similar_pairs.append((q1, q2, 1.0, 'exact'))
        
        logger.info(f"Found {len(similar_pairs)} exact duplicate pairs")
        
        # Step 2: Build token index for fast candidate filtering
        # Group quotes by their first few tokens to reduce comparisons
        token_index: Dict[str, List[Quote]] = {}
        quotes_with_tokens = []
        
        for quote in quotes:
            tokens = self.tokenize_text(quote.text)
            if tokens:
                # Use first token as index key (most quotes will have unique first words)
                first_token = sorted(tokens)[0]  # Use sorted for consistency
                if first_token not in token_index:
                    token_index[first_token] = []
                token_index[first_token].append(quote)
                quotes_with_tokens.append((quote, tokens))
        
        logger.info(f"Built token index with {len(token_index)} unique first tokens")
        
        # Step 3: Find similar quotes using token-based candidate filtering
        processed_normalized = set()  # Track normalized texts already processed
        processed_pairs = set()  # Track pairs already compared
        comparisons = 0
        token_similar_pairs = []
        fuzzy_similar_pairs = []
        
        # Skip quotes that are exact matches (already handled)
        for normalized, quote_list in normalized_to_quotes.items():
            if len(quote_list) > 1:
                processed_normalized.add(normalized)
        
        for i, (quote1, tokens1) in enumerate(quotes_with_tokens):
            if i % 500 == 0 and i > 0:
                logger.info(
                    f"Progress: {i}/{len(quotes_with_tokens)} quotes processed, "
                    f"{len(token_similar_pairs)} token matches, "
                    f"{len(fuzzy_similar_pairs)} fuzzy matches found..."
                )
            
            # Skip if already processed as exact match
            normalized1 = self.normalize_text(quote1.text)
            if normalized1 in processed_normalized:
                continue
            
            # Find candidate quotes that share at least one token
            candidates = set()
            for token in tokens1:
                if token in token_index:
                    candidates.update(token_index[token])
            
            # Remove self and already processed exact matches
            candidates.discard(quote1)
            candidates = [q for q in candidates if self.normalize_text(q.text) not in processed_normalized]
            
            # Quick length filter: skip if length difference is too large
            len1 = len(quote1.text)
            max_len_diff = max(len1 * 0.5, 50)  # Allow up to 50% length difference or 50 chars
            
            for quote2 in candidates:
                # Skip if already compared (avoid duplicate pairs)
                pair_key = tuple(sorted([quote1.id, quote2.id]))
                if pair_key in processed_pairs:
                    continue
                
                # Quick length check
                len2 = len(quote2.text)
                if abs(len1 - len2) > max_len_diff:
                    continue
                
                # Skip if in same bilingual group (they're translations)
                if (quote1.bilingual_group_id and quote2.bilingual_group_id and
                    quote1.bilingual_group_id == quote2.bilingual_group_id):
                    continue
                
                comparisons += 1
                processed_pairs.add(pair_key)
                
                # Try token similarity first (faster)
                token_score = self.calculate_token_similarity(quote1.text, quote2.text)
                
                if token_score >= self.token_threshold:
                    token_similar_pairs.append((quote1, quote2, token_score, 'token'))
                elif min(len1, len2) >= self.min_length_for_fuzzy:
                    # Only do expensive fuzzy matching if token similarity is close
                    if token_score >= 0.5:  # At least 50% token overlap to try fuzzy
                        fuzzy_score = self.calculate_fuzzy_similarity(quote1.text, quote2.text)
                        if fuzzy_score >= self.fuzzy_threshold:
                            fuzzy_similar_pairs.append((quote1, quote2, fuzzy_score, 'fuzzy'))
            
            processed_normalized.add(normalized1)
        
        # Combine all similar pairs
        similar_pairs.extend(token_similar_pairs)
        similar_pairs.extend(fuzzy_similar_pairs)
        
        logger.info(
            f"Completed: {comparisons:,} comparisons made "
            f"(vs {total_quotes * (total_quotes - 1) // 2:,} in naive approach)"
        )
        logger.info(
            f"Found {len(similar_pairs)} similar pairs: "
            f"{len([p for p in similar_pairs if p[3] == 'exact'])} exact, "
            f"{len(token_similar_pairs)} token, "
            f"{len(fuzzy_similar_pairs)} fuzzy"
        )
        
        return similar_pairs
    
    def deduplicate_by_language(
        self,
        language: str,
        dry_run: bool = False
    ) -> Dict:
        """
        Deduplicate quotes for a specific language.
        
        Args:
            language: Language code ('en' or 'ru')
            dry_run: If True, only report what would be done
            
        Returns:
            Dictionary with deduplication statistics
        """
        stats = {
            'language': language,
            'quotes_processed': 0,
            'similar_pairs_found': 0,
            'duplicate_groups': 0,
            'quotes_merged': 0,
            'quotes_removed': 0,
            'translation_links_updated': 0,
            'bilingual_groups_merged': 0,
            'similarity_methods': {'exact': 0, 'token': 0, 'fuzzy': 0}
        }
        
        # Find similar quotes
        similar_pairs = self.find_similar_quotes(language)
        stats['similar_pairs_found'] = len(similar_pairs)
        
        if not similar_pairs:
            return stats
        
        # Group similar quotes into duplicate groups
        # Use a union-find approach to group connected quotes
        quote_groups: Dict[int, Set[int]] = {}
        
        for quote1, quote2, score, method in similar_pairs:
            id1, id2 = quote1.id, quote2.id
            
            # Find groups for both quotes
            group1 = None
            group2 = None
            
            for group_id, quote_ids in quote_groups.items():
                if id1 in quote_ids:
                    group1 = group_id
                if id2 in quote_ids:
                    group2 = group_id
            
            # Merge groups or create new group
            if group1 and group2:
                if group1 != group2:
                    # Merge groups
                    quote_groups[group1].update(quote_groups[group2])
                    del quote_groups[group2]
            elif group1:
                quote_groups[group1].add(id2)
            elif group2:
                quote_groups[group2].add(id1)
            else:
                # Create new group
                new_group_id = id1
                quote_groups[new_group_id] = {id1, id2}
        
        stats['duplicate_groups'] = len(quote_groups)
        
        # Process each duplicate group
        for group_id, quote_ids in quote_groups.items():
            if len(quote_ids) < 2:
                continue
            
            # Get quote objects
            quotes = self.db.query(Quote).filter(Quote.id.in_(quote_ids)).all()
            stats['quotes_processed'] += len(quotes)
            
            # Merge quotes
            merge_stats = self.merge_quotes(quotes, dry_run=dry_run)
            
            stats['quotes_merged'] += merge_stats['merged']
            stats['quotes_removed'] += merge_stats['removed']
            stats['translation_links_updated'] += merge_stats['links_updated']
            stats['bilingual_groups_merged'] += merge_stats.get('groups_merged', 0)
            
            # Track similarity method (use method from first pair found)
            for quote1, quote2, score, method in similar_pairs:
                if quote1.id in quote_ids or quote2.id in quote_ids:
                    if method in stats['similarity_methods']:
                        stats['similarity_methods'][method] += 1
                    break
        
        return stats

