Replace:
- backend/app/services/video_processor.py

What this version does:
- detects the plate before blur
- keeps the plate sharp
- blurs everything else
- uses temporal tracking so the plate stays visible through short misses
- keeps the existing public function names/signatures used by the repo

This is the safest direct replacement because it avoids changing routers or frontend code.
