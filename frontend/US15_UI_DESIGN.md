# US-15 UI Design: TipModal Component

## Visual Design Specification

### Layout Overview

```
┌─────────────────────────────────────────────┐
│  [X Close Button]                           │
│                                             │
│         ✓  [Green Circle Icon]             │
│                                             │
│           Nice work!                        │
│   You checked in to Vision Health Check    │
│                                             │
├─────────────────────────────────────────────┤
│  ⚡ Your Personalized Tip                   │
│  ┌───────────────────────────────────────┐ │
│  │ [Yellow/Amber Gradient Background]    │ │
│  │                                       │ │
│  │ Excellent work prioritizing your     │ │
│  │ vision health! Remember to follow    │ │
│  │ the 20-20-20 rule when using         │ │
│  │ screens: every 20 minutes, look at   │ │
│  │ something 20 feet away for 20        │ │
│  │ seconds.                             │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  Campus Resource                            │
│  ┌───────────────────────────────────────┐ │
│  │ [Blue Background with Left Border]    │ │
│  │                                       │ │
│  │ Campus Health Services offers vision  │ │
│  │ screening appointments. Call          │ │
│  │ (661) 654-3277 to schedule.          │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  Next Step                                  │
│  ┌───────────────────────────────────────┐ │
│  │ [Purple Background with Left Border]  │ │
│  │                                       │ │
│  │ Consider getting an annual eye exam,  │ │
│  │ especially if you use screens         │ │
│  │ frequently for work or study.        │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  Your Progress                              │
│  1 of 8 tasks complete                      │
│  ┌───────────────────────────────────────┐ │
│  │ ████░░░░░░░░░░░░░░░░░░░░░░ [12.5%]  │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  Complete 4 more required tasks to be       │
│  prize eligible                             │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │        Continue                      │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Color Palette

### Success Header
- Icon Background: `#dcfce7` (light green)
- Icon Color: `#16a34a` (green)
- Title: `#111` (near black)
- Subtitle: `#666` (gray)

### Personalized Tip Section
- Background: Linear gradient `#fef3c7` → `#fde68a` (yellow/amber)
- Icon Color: `#92400e` (dark amber)
- Text Color: `#78350f` (darker amber)
- Border Radius: `12px`

### Campus Resource Section
- Background: `#f0f9ff` (light blue)
- Border Left: `4px solid #0ea5e9` (bright blue)
- Label Color: `#0369a1` (blue)
- Text Color: `#075985` (dark blue)
- Border Radius: `8px`

### Next Step Section
- Background: `#f5f3ff` (light purple)
- Border Left: `4px solid #8b5cf6` (purple)
- Label Color: `#6d28d9` (purple)
- Text Color: `#5b21b6` (dark purple)
- Border Radius: `8px`

### Progress Section
- Track: `#e5e5e5` (light gray)
- Fill: Linear gradient `#16a34a` → `#22c55e` (green)
- Label: `#333` (dark gray)
- Count: `#666` (gray)

### Prize Eligible Badge
- Background: `#dcfce7` (light green)
- Border: `1px solid #86efac` (green)
- Text Color: `#166534` (dark green)

### Continue Button
- Background: Linear gradient `#3b82f6` → `#2563eb` (blue)
- Text: `white`
- Hover: Darker gradient + lift effect
- Border Radius: `8px`

## Typography

### Headings
- Main Title ("Nice work!"): `1.75rem`, `700` weight
- Subtitle: `1rem`, `400` weight
- Section Headers: `1.125rem`, `600` weight
- Section Labels: `0.875rem`, `600` weight, uppercase

### Body Text
- Tip Text: `1rem`, `400` weight, `1.6` line-height
- Resource/Next Step: `0.9375rem`, `400` weight, `1.6` line-height
- Progress Count: `0.875rem`, `400` weight

## Spacing

### Modal
- Padding: `2rem` (desktop), `1.5rem` (mobile)
- Max Width: `600px`
- Border Radius: `16px`

### Sections
- Margin Between: `1.5rem`
- Section Padding: `1.5rem` (tip), `1rem–1.25rem` (resource/next step)

### Progress Bar
- Height: `8px`
- Border Radius: `4px`
- Margin: `0.5rem` (header to bar)

## Animations

### Modal Entrance
```css
@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
```
- Duration: `0.3s`
- Easing: `ease-out`

### Backdrop Entrance
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
```
- Duration: `0.2s`
- Easing: `ease-out`

### Progress Bar Fill
- Transition: `width 0.6s ease-out`
- Smooth animated fill on render

### Button Hover
- Transform: `translateY(-1px)`
- Shadow: `0 4px 12px rgba(37, 99, 235, 0.3)`
- Transition: `all 0.2s`

## Responsive Breakpoints

### Desktop (> 640px)
- Modal: `600px` max-width, centered
- Padding: `2rem`
- Title: `1.75rem`

### Mobile (≤ 640px)
- Modal: Full width with `1rem` margin
- Padding: `1.5rem`
- Title: `1.5rem`
- Reduced tip padding: `1.25rem`

## Accessibility Features

### Focus States
- Close button: Gray background on hover
- Continue button: Darker gradient on hover
- Keyboard focus: Visible outline (browser default)

### ARIA Attributes
```html
<div role="dialog" aria-modal="true" aria-labelledby="tip-modal-title">
  <h2 id="tip-modal-title">Nice work!</h2>
  <div role="progressbar" aria-valuenow="1" aria-valuemin="0" 
       aria-valuemax="8" aria-label="Challenge progress"></div>
</div>
```

### Keyboard Navigation
- `Escape`: Closes modal
- `Tab`: Navigates through close button and continue button
- `Enter`/`Space`: Activates buttons

## States

### Loading State (during check-in)
- "Check in" button shows "Checking in…"
- Button is disabled
- Cursor: `not-allowed`

### Success State (tip shown)
- Modal appears with animation
- All content rendered
- Continue button enabled

### Error State (future enhancement)
- Could show error message in place of modal
- Retry button option

### Already Checked In
- Returns generic tip: "You've already checked in to this task!"
- Same modal structure, different content

## Interactive Elements

### Buttons
1. **Close Button (×)**
   - Position: Top-right corner
   - Size: `32px × 32px`
   - Circular hover background
   - Color transitions on hover

2. **Continue Button**
   - Full width
   - Prominent blue gradient
   - Lift animation on hover
   - Active state (pressed down)

### Click Targets
- Backdrop: Closes modal
- Modal content: Stops propagation (doesn't close)
- Close button: Closes modal
- Continue button: Closes modal

## Content Structure

### Header
```
Icon (✓ checkmark in green circle)
  ↓
Title: "Nice work!"
  ↓
Subtitle: "You checked in to {task_title}"
  ↓
Divider line
```

### Main Content
```
Section 1: Your Personalized Tip
  Icon (⚡) + Heading
  Tip text (2-3 sentences)

Section 2: Campus Resource
  Label + Resource text

Section 3: Next Step
  Label + Next step text

Section 4: Progress
  "Your Progress" + count
  Progress bar (visual)
  Prize status message
```

### Footer
```
Continue button (call-to-action)
```

## Example Content

### Sample Tip (Vision Task)
```
Tip: "Excellent work prioritizing your vision health! Remember 
      to follow the 20-20-20 rule when using screens: every 20 
      minutes, look at something 20 feet away for 20 seconds."

Resource: "Campus Health Services offers vision screening 
           appointments. Call (661) 654-3277 to schedule."

Next Step: "Consider getting an annual eye exam, especially if 
            you use screens frequently for work or study."
```

### Sample Tip (Nutrition Task)
```
Tip: "Great job engaging with nutrition education! The 
      Mediterranean diet pattern you learned about can help 
      reduce chronic disease risk and boost energy levels."

Resource: "Visit the campus dining nutrition page at 
           shs.edu/nutrition for recipes and meal planning tips."

Next Step: "Try adding one more serving of vegetables to your 
            meals this week."
```

## Technical Implementation Notes

### CSS Modules
- All styles scoped to component
- No global style pollution
- BEM-like naming within module

### Performance
- Modal rendered conditionally (only when needed)
- No expensive calculations on render
- Smooth 60fps animations

### Browser Support
- Modern CSS (Grid, Flexbox)
- CSS Custom Properties (optional, has fallbacks)
- Graceful degradation for older browsers

## Design Rationale

### Color Coding
- **Yellow/Amber** for tips: Warm, attention-grabbing, positive
- **Blue** for resources: Professional, trustworthy, informative
- **Purple** for next steps: Action-oriented, forward-looking
- **Green** for success/progress: Achievement, growth, wellness

### Visual Hierarchy
1. Success icon (first thing you see)
2. Title and task name
3. Personalized tip (largest, most colorful section)
4. Supporting information (resources, next steps)
5. Progress tracking (motivational)
6. Call-to-action button (clear next step)

### User Experience
- Immediate positive reinforcement ("Nice work!")
- Relevant health information (personalized tip)
- Practical resources (actionable contact info)
- Clear progress (visual bar + text)
- Motivation to continue (prize eligibility)
- Easy to dismiss (multiple close options)

This design creates a rewarding, educational moment after each check-in while maintaining professional aesthetics and accessibility standards.
