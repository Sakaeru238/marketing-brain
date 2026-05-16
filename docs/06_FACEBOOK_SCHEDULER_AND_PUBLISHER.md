# 06 — Facebook Scheduler and Publisher

## Scheduler entry point

```bash
python -m core.jobs.daily_schedule_facebook_job
```

## Responsibility

The scheduler:
- reads `Organic_Posts`,
- processes only rows where `post_status = ready`,
- maps route/page configuration,
- computes schedule times when needed,
- posts or schedules to Facebook,
- updates publisher status fields only.

## Required status rule

Only this status is processed:

```text
ready
```

Rows already marked:
```text
posted
error
```

are skipped.

## Important observed behavior

A terminal summary such as:

```json
"success_status": "posted",
"processed": 0,
"skipped": 34
```

does **not** mean posts were scheduled.  
It means:
- the job’s success target status is `posted`,
- but no rows matched `ready`,
- therefore nothing was processed.

## Route resolution

The scheduler maps:
- brand ID,
- page URL,
- platform ID

against:
```text
config/google_sheet_routing.json
```

The real Facebook/Meta page ID is taken from routing config, not invented from sheet display IDs.

## Target timezone

Scheduling must use:
```text
Page_Channel_Library.target_timezone
```

For example:
```text
America/New_York
```

The host machine may be in Vietnam.  
Scheduling math must still use target audience timezone + UTC conversions.

## Scheduling windows

Default heuristic slots exist for:
- morning,
- lunch,
- after work,
- evening scroll.

The scheduler computes a future UTC schedule time that meets validator constraints.

## Publisher write constraints

The scheduler may update only job-control fields such as:
- `post_status`
- `publisher_status`
- `facebook_post_id`
- `publisher_error`
- `published_or_scheduled_at`
- `scheduled_datetime_utc`

It must **not** rewrite:
- post text,
- image URL,
- hook,
- content tags,
- content pillar,
- user notes.

## Dry run vs real run

### Dry run
Environment:
```env
FACEBOOK_PUBLISH_DRY_RUN=true
```

Expected result:
```text
scheduled_dry_run
```

Dry run should not create a real Facebook post.

### Real schedule/publish
Environment:
```env
FACEBOOK_PUBLISH_DRY_RUN=false
```

Expected result:
```text
scheduled
```
or another success status based on endpoint behavior.

## Hashtag formatting rule

Google Sheet stores:
```text
#VietnameseCoffee|#CoffeeHeritage|#VietnameseFamily
```

Publisher converts this to:
```text
#VietnameseCoffee #CoffeeHeritage #VietnameseFamily
```

It must:
- keep exactly one `#`,
- not output `##VietnameseCoffee`,
- preserve display casing,
- split on pipe/comma/semicolon/newline where applicable,
- avoid duplicate hashtag append if already present in message.

## Publishing endpoint selection

If `image_url` exists:
```text
photos endpoint / photo scheduling path
```

If `image_url` is empty:
```text
feed endpoint / message-only scheduling path
```

## Current known open issue

Organic generation/export was observed producing rows in `Organic_Posts` with:
```text
post_status = posted
```

This blocks scheduler processing because it only accepts:
```text
ready
```

See `10_CURRENT_STATE_KNOWN_ISSUES_AND_NEXT_WORK.md`.
