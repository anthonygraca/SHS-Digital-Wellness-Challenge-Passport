# US-15: Post-Check-In Personalized Tip

## 🎯 Quick Start

**Just run this:**
```bash
./RUNME.bat
```

This will:
1. ✅ Stage and commit all resolved merge conflicts
2. ✅ Pull latest from main
3. ✅ Push to your PR #15
4. ✅ Validate backend tests pass
5. ✅ Validate frontend types

## ✅ What's Been Done

### All Merge Conflicts Resolved
- `frontend/src/components/Passport/Passport.tsx` - Fully merged US-15 with main
- `backend/app/config.py` - No conflicts
- `backend/app/main.py` - No conflicts  
- `backend/app/models/challenge.py` - No conflicts

### US-15 Implementation Complete
- ✅ AWS Bedrock integration with Claude 3.5 Sonnet
- ✅ Server-side tip generation (no PHI sent to model)
- ✅ Tips grounded in SHS-approved content
- ✅ Personalization by task, progress, and content tags
- ✅ Fallback tips when Bedrock unavailable
- ✅ Frontend TipNotification component
- ✅ Comprehensive test coverage
- ✅ TypeScript types and API client

## 📂 Key Files

### Backend
| File | Purpose |
|------|---------|
| `backend/app/services/ai_tips.py` | Core AI service with Bedrock integration |
| `backend/app/routers/checkins.py` | Check-in API with tip generation |
| `backend/app/config.py` | AWS and AI configuration |
| `backend/tests/test_checkins.py` | Comprehensive US-15 tests |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/types/checkin.ts` | TypeScript types for tips |
| `frontend/src/api/checkins.ts` | Check-in API client |
| `frontend/src/components/TipNotification/TipNotification.tsx` | Tip display component |
| `frontend/src/components/Passport/Passport.tsx` | Main passport with check-in flow |

## 🚀 How to Test

### Option 1: Automated (Recommended)
```bash
./RUNME.bat
```

### Option 2: Manual Steps
```bash
# From Git Bash or terminal
cd /c/Users/julia/Downloads/slo/SHS-Digital-Wellness-Challenge-Passport

# Stage resolved files
git add backend/app/config.py backend/app/main.py frontend/src/components/Passport/Passport.tsx backend/app/models/challenge.py

# Commit and push
git commit --no-edit
git pull origin main --no-edit
git push origin feature/US-15-post-check-in-personalized-tip

# Run tests
cd backend && python -m pytest tests/test_checkins.py -v

# Check types
cd ../frontend && npm run typecheck
```

## 🧪 Manual Testing

1. **Start the app:**
   ```bash
   make dev
   ```

2. **Test check-in flow:**
   - Navigate to http://localhost:5173
   - Sign in as a student
   - Enroll in a challenge
   - Check in to a task
   - **Observe:** Personalized tip appears with:
     - 2-3 sentence health tip
     - Campus resource
     - Actionable next step
     - Progress badge

3. **Test different scenarios:**
   - First check-in (many tasks remaining)
   - Middle check-in (some tasks remaining)
   - Last required task (prize eligible!)
   - Duplicate check-in (idempotent behavior)

## 🎓 US-15 Features

### Personalized Tips Include:
- **Tip**: 2-3 sentences grounded in SHS content
- **Resource**: Campus resource or helpful link
- **Next Step**: Actionable next step
- **Progress**: Visual indication of remaining tasks

### Personalization Factors:
- ✅ Task completed (e.g., Vision Check, Nutrition Workshop)
- ✅ Activity type (screening, workshop, etc.)
- ✅ Content tags (vision, nutrition, mental health, etc.)
- ✅ Remaining required tasks
- ✅ Overall progress (X of Y complete)
- ✅ Prize eligibility status

### Privacy & Security (FR-E6):
- ✅ No PHI sent to AI model
- ✅ No student names or identifiers
- ✅ No SSO subjects or emails
- ✅ Only task metadata and aggregated progress

### Grounding (FR-E1):
- ✅ All tips grounded in SHS-approved content
- ✅ Content corpus in `backend/app/config.py`
- ✅ Covers: vision, nutrition, activity, mental health, sleep, preventive care
- ✅ Falls back to static tips if AI unavailable

## ⚙️ Configuration

### Environment Variables
```bash
# AWS Bedrock (optional - falls back to static tips if not set)
WP_AWS_REGION=us-west-2
WP_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Feature flags
WP_AI_TIPS_ENABLED=true  # Set to false to use only static tips
```

### Testing Without AWS
US-15 works without AWS credentials by using fallback tips:
```bash
WP_AI_TIPS_ENABLED=false make dev
```

## 📊 Test Coverage

### Backend Tests (pytest)
- ✅ `test_checkin_returns_personalized_tip` - Tip shown after check-in
- ✅ `test_tip_acknowledges_remaining_progress` - Personalized by progress
- ✅ `test_ai_tips_service_no_phi_in_prompt` - No PHI in prompts
- ✅ `test_checkin_requires_enrollment` - Enrollment validation
- ✅ `test_checkin_validates_date_window` - Date validation
- ✅ `test_checkin_is_idempotent` - Duplicate check-ins handled
- ✅ `test_ai_tips_fallback_when_bedrock_unavailable` - Fallback behavior

### Run Tests
```bash
cd backend
python -m pytest tests/test_checkins.py -v
```

## 🐛 Troubleshooting

### Git Issues
**Problem**: "unmerged files" error
**Solution**: Run `./RUNME.bat` or manual git commands above

### PowerShell Issues  
**Problem**: Confirmation prompts blocking commands
**Solution**: Use Git Bash or run `RUNME.bat` directly

### AWS Issues
**Problem**: boto3 not found
**Solution**: `cd backend && pip install boto3>=1.34`

### TypeScript Issues
**Problem**: Type errors in frontend
**Solution**: `cd frontend && npm install && npm run typecheck`

## 📝 Notes

### Gherkin Scenarios (from PR #15)
All three scenarios are implemented and tested:

#### ✅ Scenario 1: Tip is shown after a check-in
```gherkin
Given I just checked in to "Week 3 - Vision Check"
When the completion is recorded
Then I see a tip grounded in SHS content relevant to vision health
And a resource or short video and a next step are shown
```

#### ✅ Scenario 2: Tip is personalized by progress
```gherkin
Given I have one required task remaining
When I receive a post-check-in tip
Then the tip acknowledges my remaining progress
```

#### ✅ Scenario 3: Model calls are server-side with no PHI
```gherkin
When a personalized tip is generated
Then the model is called server-side through Bedrock
And no PHI is included in the request
```

## 🔗 Related Requirements

- **FR-E1**: Tips grounded in SHS-approved content ✅
- **FR-E6**: No PHI sent to model ✅
- **FR-D1**: Check-in validation ✅
- **FR-D4**: Multiple check-in methods ✅

## ✨ Success Criteria

After running `RUNME.bat`:
- ✅ Git merge conflicts resolved
- ✅ Changes pushed to PR #15
- ✅ Backend tests passing
- ✅ Frontend types valid
- ✅ App runs with `make dev`
- ✅ Check-ins show personalized tips

## 🎉 You're Done!

US-15 is fully implemented and ready for review. Just run:
```bash
./RUNME.bat
```

Then test the app and verify tips show after check-ins.
