# Run Alembic from backend folder (alembic may not be on PATH)
# Usage: .\run_alembic.ps1 upgrade head   or   .\run_alembic.ps1 stamp 20260314_0001
Set-Location $PSScriptRoot
python -m alembic @args
