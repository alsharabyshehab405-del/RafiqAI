# Subscriptions

Plans are Free / Pro / Premium.

Google Play purchase tokens are verified server-side. Android cannot grant itself a paid entitlement.

Backend handles:

- active
- pending
- grace period
- cancelled-before-expiry
- on-hold where provider payload supports it
- expired
- restore
- token/account ownership conflicts

Configure product IDs and actual prices through environment variables. Never hardcode real service credentials in Android.
