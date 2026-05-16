# Architecture

Visual Spec
 → Render layout
 → Generate scene images
 → Evaluate score
 → Retry until score >= 9
 → Upload to CDN
 → Write back to sheet
 → Await user feedback
 → Feed feedback to next run
