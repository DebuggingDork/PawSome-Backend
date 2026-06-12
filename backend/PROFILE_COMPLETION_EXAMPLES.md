# Profile Completion API - Examples

## Endpoint
`GET /users/me/completion`

**Authentication:** Required (Bearer token)

## Response Schema

```json
{
  "completion_percentage": 85,
  "is_complete": true,
  "completed_fields": ["profile_photo", "full_name", "occupation", "bio", "pet_created", "pet_photo"],
  "missing_fields": ["address"],
  "suggestions": ["Add your address (only visible to matches) for meetups"],
  "profile_fields_complete": 80,
  "pet_profile_complete": 100,
  "total_pets": 1,
  "active_pets": 1,
  "has_profile_photo": true,
  "has_basic_info": true,
  "has_bio": true,
  "has_address": false,
  "has_at_least_one_pet": true,
  "has_active_pet": true
}
```

## Example Scenarios

### 1. Brand New User (Just Registered)

```json
{
  "completion_percentage": 0,
  "is_complete": false,
  "completed_fields": [],
  "missing_fields": [
    "profile_photo",
    "full_name",
    "occupation",
    "bio",
    "address",
    "pet_created",
    "pet_photo"
  ],
  "suggestions": [
    "Add your name so pet owners know who you are",
    "Upload a profile photo to build trust",
    "Share your occupation to help others get to know you",
    "Write a bio about yourself and your pet preferences",
    "Create your first pet profile to start matching"
  ],
  "profile_fields_complete": 0,
  "pet_profile_complete": 0,
  "total_pets": 0,
  "active_pets": 0,
  "has_profile_photo": false,
  "has_basic_info": false,
  "has_bio": false,
  "has_address": false,
  "has_at_least_one_pet": false,
  "has_active_pet": false
}
```

**Frontend UI Suggestion:**
- Show progress bar at 0%
- Display prominent "Complete Your Profile" banner
- Show checklist of missing items with icons
- Primary CTA: "Add Your Name and Photo"

---

### 2. User Added Basic Info (Name & Occupation)

```json
{
  "completion_percentage": 24,
  "is_complete": false,
  "completed_fields": ["full_name", "occupation"],
  "missing_fields": [
    "profile_photo",
    "bio",
    "address",
    "pet_created",
    "pet_photo"
  ],
  "suggestions": [
    "Upload a profile photo to build trust",
    "Write a bio about yourself and your pet preferences",
    "Create your first pet profile to start matching"
  ],
  "profile_fields_complete": 40,
  "pet_profile_complete": 0,
  "total_pets": 0,
  "active_pets": 0,
  "has_profile_photo": false,
  "has_basic_info": true,
  "has_bio": false,
  "has_address": false,
  "has_at_least_one_pet": false,
  "has_active_pet": false
}
```

**Progress:** 24% (2/5 profile fields × 60% = 24%)

---

### 3. User Completed Profile, Created Pet (No Photo Yet)

```json
{
  "completion_percentage": 80,
  "is_complete": false,
  "completed_fields": [
    "profile_photo",
    "full_name",
    "occupation",
    "bio",
    "address",
    "pet_created"
  ],
  "missing_fields": ["pet_photo"],
  "suggestions": [
    "Upload at least one photo of your pet to activate their profile"
  ],
  "profile_fields_complete": 100,
  "pet_profile_complete": 50,
  "total_pets": 1,
  "active_pets": 0,
  "has_profile_photo": true,
  "has_basic_info": true,
  "has_bio": true,
  "has_address": true,
  "has_at_least_one_pet": true,
  "has_active_pet": false
}
```

**Progress:** 80% (100% profile × 60% + 50% pet × 40% = 80%)

**Critical State:** Pet created but not active! This is the most important next step.

---

### 4. Fully Complete Profile 🎉

```json
{
  "completion_percentage": 100,
  "is_complete": true,
  "completed_fields": [
    "profile_photo",
    "full_name",
    "occupation",
    "bio",
    "address",
    "pet_created",
    "pet_photo"
  ],
  "missing_fields": [],
  "suggestions": [
    "🎉 Your profile is complete! Start swiping to find matches"
  ],
  "profile_fields_complete": 100,
  "pet_profile_complete": 100,
  "total_pets": 1,
  "active_pets": 1,
  "has_profile_photo": true,
  "has_basic_info": true,
  "has_bio": true,
  "has_address": true,
  "has_at_least_one_pet": true,
  "has_active_pet": true
}
```

**Frontend UI Suggestion:**
- Show celebration animation 🎉
- Hide onboarding banners
- Show "Start Swiping" CTA prominently
- Maybe show a badge: "Profile Complete ✓"

---

### 5. Minimal Complete (Ready to Match)

```json
{
  "completion_percentage": 68,
  "is_complete": true,
  "completed_fields": [
    "profile_photo",
    "full_name",
    "occupation",
    "pet_created",
    "pet_photo"
  ],
  "missing_fields": ["bio", "address"],
  "suggestions": [
    "Write a bio about yourself and your pet preferences",
    "Add your address (only visible to matches) for meetups"
  ],
  "profile_fields_complete": 60,
  "pet_profile_complete": 100,
  "total_pets": 1,
  "active_pets": 1,
  "has_profile_photo": true,
  "has_basic_info": true,
  "has_bio": false,
  "has_address": false,
  "has_at_least_one_pet": true,
  "has_active_pet": true
}
```

**Note:** `is_complete: true` because minimum threshold met:
- ✅ Has profile photo
- ✅ Has basic info (name + occupation)
- ✅ Has active pet

User can start matching, but encouraged to complete bio/address.

---

## Calculation Logic

### Overall Completion Percentage
```
Overall = (Profile Fields × 60%) + (Pet Profile × 40%)
```

### Profile Fields Percentage
```
Profile = (completed_count / 5) × 100
```

Fields counted:
1. profile_photo
2. full_name
3. occupation
4. bio
5. address

### Pet Profile Percentage
```
If no pets: 0%
If pet created but not active: 50%
If has active pet: 100%
```

### Is Complete Threshold
Profile is considered "complete" when:
- ✅ Has profile photo
- ✅ Has basic info (name AND occupation)
- ✅ Has at least one active pet

Bio and address are optional but encouraged.

---

## Frontend Integration Ideas

### 1. Progress Bar Component
```jsx
<ProgressBar 
  percentage={completion.completion_percentage}
  color={completion.is_complete ? "green" : "blue"}
/>
```

### 2. Onboarding Checklist
```jsx
<Checklist>
  {completion.missing_fields.map(field => (
    <ChecklistItem key={field} status="incomplete">
      {getFieldLabel(field)}
    </ChecklistItem>
  ))}
  {completion.completed_fields.map(field => (
    <ChecklistItem key={field} status="complete">
      {getFieldLabel(field)}
    </ChecklistItem>
  ))}
</Checklist>
```

### 3. Smart Suggestions
```jsx
<SuggestionCard>
  <h3>Next Steps</h3>
  {completion.suggestions.map(suggestion => (
    <Suggestion key={suggestion}>
      {suggestion}
    </Suggestion>
  ))}
</SuggestionCard>
```

### 4. Milestone Badges
```jsx
{completion.has_profile_photo && <Badge>📸 Photo Added</Badge>}
{completion.has_basic_info && <Badge>👤 Profile Setup</Badge>}
{completion.has_active_pet && <Badge>🐕 Pet Active</Badge>}
{completion.is_complete && <Badge variant="success">✨ Complete</Badge>}
```

### 5. Conditional Navigation
```jsx
// Block certain features until profile is complete
{!completion.has_active_pet && (
  <Alert>
    Upload a pet photo to start swiping!
  </Alert>
)}

{completion.is_complete && (
  <Button primary onClick={goToSwipe}>
    Start Finding Matches
  </Button>
)}
```

---

## Gamification Ideas

### Level System
- **Level 1 (0-24%)**: Newcomer 🐣
- **Level 2 (25-49%)**: Getting Started 🌱
- **Level 3 (50-74%)**: Almost There 🚀
- **Level 4 (75-99%)**: Nearly Complete ⭐
- **Level 5 (100%)**: Profile Master 🏆

### Achievement Unlocks
- "First Steps" - Add your name
- "Show Your Face" - Upload profile photo
- "Pet Parent" - Create first pet profile
- "Picture Perfect" - Upload pet photo
- "Fully Loaded" - Complete all fields

### Progress Rewards
- 50% complete → Unlock bio customization
- 75% complete → See who viewed your pets
- 100% complete → Priority in search results

---

## Testing the Endpoint

### cURL Example
```bash
curl -X GET "http://localhost:8000/users/me/completion" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Response Validation
- `completion_percentage` is always 0-100
- `is_complete` is true when minimum threshold met
- `suggestions` always has at least one item
- `completed_fields` + `missing_fields` = 7 total fields
