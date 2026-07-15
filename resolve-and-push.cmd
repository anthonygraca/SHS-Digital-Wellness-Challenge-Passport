@echo off
git add backend/app/models/challenge.py
git add frontend/src/components/Passport/Passport.tsx
git rebase --continue
git push -f origin feature/US-15-post-check-in-personalized-tip
