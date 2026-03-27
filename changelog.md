# Changelog

---

## v1.0.0 — Initial Release

### Features
- Smart search (exact match, keyword match, fuzzy match)
- Structured objection responses (soft, medium, hard)
- Google Sheets integration (Lib and Log)
- Add new objection via UI

---

### Analytics
- Top objections by selected period
- Date range filtering
- Tracking based on real usage logs

---

### Logging System
- Buffer-based logging using session state
- Batch processing (auto flush)
- Manual sync and refresh
- Timestamp tracking for each log entry

---

### Performance Improvements
- Cached data loading (TTL 60 seconds)
- Cached logs loading
- Reduced API calls
- Retry mechanism for Google Sheets API stability

---

### UI/UX Improvements
- Click-to-copy response cards
- Improved layout and spacing
- Toast notifications for feedback
- Expander for adding new objections
- Inline sync button in analytics header

---

### Bug Fixes
- Fixed session_state modification error
- Fixed search input not clearing properly
- Fixed warning message not appearing
- Fixed keyword matching issue
- Fixed Google Sheets connection instability

---

### Optimization
- Replaced per-request logging with batch logging
- Debounced search execution
- Implemented safe API request wrapper

---

## Next Version (Planned)
- Compare mode (period-to-period analysis)
- Automatic insight generation
- Export report functionality
- Advanced multi-keyword search