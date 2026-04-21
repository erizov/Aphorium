"""News repository smoke tests (SQLite)."""

from repositories.news_repository import NewsRepository


def test_news_create_and_list(db_session):
    repo = NewsRepository(db_session)
    art = repo.create(
        title="Demo",
        content="Body text.",
        url="https://example.com/demo-news-1",
        source="unit",
        language="en",
        category="technology",
    )
    rows, total = repo.list_articles(skip=0, limit=10, preload=False)
    assert total == 1
    assert rows[0].id == art.id
    assert rows[0].title == "Demo"
