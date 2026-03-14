# UI Integration Notes

## Included changes
- Smaller review video window
- Hebrew RTL ticket review page
- Screenshot capture from blurred video player
- Timestamp overlay on screenshots based on video metadata start time + current player time
- Evidence sidebar with registry, vehicle, and parking context
- Screenshot strip saved into the ticket context

## Frontend integration
1. Import `rtl.css` once in your app root.
2. Add `TicketReviewPage.tsx` to your router.
3. Replace the mock ticket fetch with your real ticket review API.
4. Ensure the video used in the review page is the blurred evidence video, not the original unblurred source.
5. Wire the screenshot POST endpoint.

## Screenshot requirement
The screenshot capture must use the blurred player only.
The saved screenshot should be treated as immutable evidence and stored with:
- ticket id
- frame timestamp in ms
- human readable timestamp label
- source video hash
- captured user id
- save time

## Hebrew
All visible text in the patch is Hebrew-first.
For a full product conversion, extract any remaining strings from your existing components into i18n dictionaries.
