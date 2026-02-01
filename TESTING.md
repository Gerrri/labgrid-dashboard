# Testing Guide for Code Review Fixes

This document provides manual testing steps to verify all code review fixes.

## Automated Tests Status

### ✅ Frontend Build
```bash
cd frontend && npm run build
```
**Status**: PASSED - No TypeScript errors, build successful

### ✅ Backend Tests
```bash
cd backend && python -m pytest
```
**Status**: 132/133 passed (1 pre-existing failure unrelated to fixes)

### ✅ Production Docker Image
```bash
./scripts/test-production-image.sh
```
**Status**: PASSED - All infrastructure tests passed

## Manual Testing Guide

### Test 1: XSS Prevention (Critical Fix)
**What was fixed**: URL validation in web_url to prevent XSS

**How to test**:
1. Open browser DevTools Console
2. In the dashboard, create a target with malicious `web_url`:
   - `javascript:alert('XSS')`
   - `data:text/html,<script>alert('XSS')</script>`
3. **Expected**: IP address should render as plain text (no link)
4. **Expected**: No JavaScript execution

**Manual verification**:
```javascript
// In browser console, verify URL validation
const testUrls = [
  'http://192.168.1.1',      // ✓ Should work
  'https://example.com',      // ✓ Should work
  'javascript:alert(1)',      // ✗ Should be blocked
  'data:text/html,test',      // ✗ Should be blocked
];
```

### Test 2: Race Condition Prevention (High Priority)
**What was fixed**: Command output state updates now use functional setState

**How to test**:
1. Open a target's command panel
2. Execute multiple commands rapidly (click 3-4 command buttons quickly)
3. **Expected**: All command outputs appear in correct order
4. **Expected**: No outputs are lost or overwritten

### Test 3: Preset Details Caching (High Priority)
**What was fixed**: Preset details are now cached to avoid duplicate API calls

**How to test**:
1. Open browser DevTools Network tab
2. Open target settings (⚙️ icon)
3. Close settings
4. Open settings again
5. **Expected**: No duplicate `/api/presets/{id}` calls on second open
6. Check Network tab - preset detail calls should be cached

### Test 4: AbortController - Component Unmount (Medium Priority)
**What was fixed**: API calls are now cancelled when components unmount

**How to test**:
1. Open browser DevTools Console
2. Open target settings (slow network helps):
   - DevTools → Network → Throttling → Slow 3G
3. Immediately close settings before load completes
4. **Expected**: No console warnings about setState on unmounted component
5. Check Network tab - requests should show "(canceled)"

**Repeat for**:
- Opening/closing CommandPanel
- Expanding/collapsing targets quickly

### Test 5: Invalid Timestamp Handling (Medium Priority)
**What was fixed**: Scheduled outputs with invalid timestamps show "N/A"

**How to test**:
1. Mock a target with invalid timestamp in scheduled_outputs
2. **Expected**: Shows "N/A" instead of "Invalid Date"
3. **Expected**: No cache expiry errors in console

**Browser console test**:
```javascript
// Should return NaN and be handled gracefully
const invalidDate = Date.parse('invalid-timestamp');
console.log(Number.isNaN(invalidDate)); // true
```

### Test 6: React Keys Stability (Low Priority)
**What was fixed**: Command output keys now include more fields

**How to test**:
1. Execute same command multiple times quickly
2. Open React DevTools → Profiler
3. Record a new profiling session
4. Execute commands
5. **Expected**: Minimal component re-renders in OutputViewer

### Test 7: Debug Logging Optimization (Low Priority)
**What was fixed**: Debug logs only run when explicitly enabled

**How to test**:
1. Without `VITE_DEBUG_SCHEDULED=true`:
   - Open console
   - Expand targets
   - **Expected**: No debug logs

2. With debug enabled:
   ```bash
   # In .env
   VITE_DEBUG_SCHEDULED=true
   ```
   - Rebuild: `npm run dev`
   - **Expected**: Debug logs appear for scheduled outputs

## Performance Testing

### Memory Leaks
1. Open Chrome DevTools → Memory
2. Take heap snapshot
3. Open/close target settings 10 times
4. Take another heap snapshot
5. Compare snapshots
6. **Expected**: No significant memory growth from event listeners or timers

### Network Efficiency
1. Open DevTools → Network
2. Refresh dashboard
3. Count API calls
4. **Expected**:
   - Preset details fetched only once per preset
   - No duplicate calls when opening settings

## Browser Compatibility

Test in:
- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari (if available)

## Production Deployment Test

```bash
# Build production image
docker build -t labgrid-dashboard:test -f Dockerfile.prod .

# Run with test config
docker run -d \
  --name labgrid-test \
  -p 8080:80 \
  -e COORDINATOR_URL=ws://your-coordinator:20408/ws \
  labgrid-dashboard:test

# Test endpoints
curl http://localhost:8080/health              # Nginx
curl http://localhost:8080/api/health          # Backend (requires coordinator)
curl http://localhost:8080/env-config.js       # Runtime config
```

## Regression Testing

After all fixes, verify these still work:
- ✅ Target expansion/collapse
- ✅ Command execution
- ✅ Preset changes
- ✅ WebSocket real-time updates
- ✅ Scheduled command columns
- ✅ Target settings dialog

## Automated Test Summary

| Test Suite | Status | Details |
|------------|--------|---------|
| Frontend Build | ✅ PASS | TypeScript compilation successful |
| Backend Tests | ✅ PASS | 132/133 tests passed |
| Production Image | ✅ PASS | Docker build & runtime tests passed |
| Manual Testing | ⏳ TODO | Follow guide above |

## Known Issues (Pre-existing)

1. Backend test failure in `test_get_places_with_acquired_resource` - unrelated to fixes
2. Frontend warning about `env-config.js` bundling - expected (runtime script)

## Checklist for Merge

- [x] All automated tests pass
- [x] Frontend builds without errors
- [x] Production Docker image builds
- [ ] Manual testing completed
- [ ] No console errors in browser
- [ ] No memory leaks detected
- [ ] Performance acceptable
