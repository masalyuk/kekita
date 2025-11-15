<!-- 604828ff-2276-4c02-bd7c-4e34f4df2764 3987d350-ba83-4229-9ff7-6ace2566d222 -->
# Add Debug Logging to Frontend Evolution Button

## Problem

The "Apply Evolution & Continue" button doesn't work, and we need more visibility into what's happening in the frontend to diagnose the issue.

## Solution

Add comprehensive console.log statements throughout the evolution prompt update flow to track:

1. Button click events
2. Confirmation state checks
3. API request/response details
4. Error conditions
5. WebSocket state

## Changes

### 1. Update `updatePrompts` method (`frontend/game-client.js`)

- Add debug logs at the start showing gameId, confirmation states
- Log the API request details (URL, payload)
- Log the response status and data
- Add more detailed error logging

### 2. Update button click handler (`frontend/game-client.js` around line 947)

- Add debug log when button is clicked
- Log input values
- Log confirmation states before calling updatePrompts
- Log any early returns or errors

### 3. Add WebSocket state logging

- Log WebSocket connection state when updatePrompts is called
- Check if WebSocket is still connected

## Implementation Details

- Use `console.log` with clear prefixes like `[EvolutionButton]` or `[updatePrompts]`
- Log all relevant state variables
- Log request/response details
- Log any conditions that cause early returns