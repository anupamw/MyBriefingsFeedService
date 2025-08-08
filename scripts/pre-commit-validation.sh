#!/bin/bash
"""
Pre-commit validation script for MyBriefingsFeedService.
This script runs before commits to catch import issues early.
"""

set -e

echo "🔍 Running pre-commit validation..."

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Please run this script from the project root."
    exit 1
fi

# Run import validation
echo "📋 Validating Python imports..."
python scripts/validate_imports.py

if [ $? -eq 0 ]; then
    echo "✅ All imports validated successfully!"
else
    echo "❌ Import validation failed!"
    echo "Please fix the import issues before committing."
    exit 1
fi

# Run basic syntax checks
echo "🔍 Checking Python syntax..."
find . -name "*.py" -not -path "./.venv/*" -not -path "./.git/*" -exec python -m py_compile {} \;
echo "✅ Python syntax check passed!"

# Run basic linting (if available)
if command -v flake8 &> /dev/null; then
    echo "🔍 Running flake8 linting..."
    flake8 --max-line-length=120 --ignore=E501,W503 services/feed-ingestion/ || echo "⚠️  Linting issues found (non-blocking)"
else
    echo "⚠️  flake8 not found, skipping linting"
fi

echo "🎉 Pre-commit validation completed successfully!" 