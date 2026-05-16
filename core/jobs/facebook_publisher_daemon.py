
class FacebookPublisherDaemon:
    '''
    Runs every 5 minutes.

    Logic:
    - find approved posts
    - scheduled_datetime_utc <= now + threshold
    - publisher_status empty
    - publish to Meta Graph API
    - update Google Sheet
    - notify Telegram
    '''
