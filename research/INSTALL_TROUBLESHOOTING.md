# Installation Troubleshooting

## Python 3.13 Compatibility Issues

If you encounter errors installing `pydantic-core` on Python 3.13, try these solutions:

### Solution 1: Update Build Tools (Recommended)

```bash
# Update pip, setuptools, and wheel first
python -m pip install --upgrade pip setuptools wheel

# Then install requirements
pip install -r requirements.txt
```

### Solution 2: Use Pre-built Wheels Only

```bash
# Force use of pre-built wheels (no compilation)
pip install --only-binary :all: -r requirements.txt
```

### Solution 3: Install Specific Compatible Versions

If the above doesn't work, install compatible versions manually:

```bash
pip install "pydantic>=2.6.0" "pydantic-core>=2.20.0"
pip install -r requirements.txt
```

### Solution 4: Use Python 3.11 or 3.12

Python 3.13 is very new and some packages may not have pre-built wheels yet.
Consider using Python 3.11 or 3.12 for better compatibility:

```bash
# Check your Python version
python --version

# If using Python 3.13, consider installing Python 3.12
# Download from: https://www.python.org/downloads/
```

### Solution 5: Install Rust (Advanced)

If you need to compile from source, install Rust:

1. Download Rust from: https://rustup.rs/
2. Run the installer
3. Restart your terminal
4. Try installing again: `pip install -r requirements.txt`

## Common Errors

### Error: "metadata-generation-failed"

**Cause:** Package needs to be compiled but build tools are missing or incompatible.

**Fix:**
```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Error: "Cargo not found" or "Rust not found"

**Cause:** Package requires Rust to compile.

**Fix:** Use Solution 1-4 above, or install Rust (Solution 5).

### Error: "Microsoft Visual C++ 14.0 or greater is required"

**Cause:** Some packages need C++ compiler on Windows.

**Fix:**
1. Install Microsoft C++ Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Or use pre-built wheels: `pip install --only-binary :all: -r requirements.txt`

## Quick Fix Script

Run this to fix most common issues:

**Windows (PowerShell):**
```powershell
python -m pip install --upgrade pip setuptools wheel
pip install --only-binary :all: pydantic pydantic-core
pip install -r requirements.txt
```

**Linux/Mac:**
```bash
python3 -m pip install --upgrade pip setuptools wheel
pip install --only-binary :all: pydantic pydantic-core
pip install -r requirements.txt
```

## Verify Installation

After installation, verify everything works:

```bash
python -c "import fastapi, sqlalchemy, pydantic; print('OK')"
```

If you see "OK", installation was successful!

