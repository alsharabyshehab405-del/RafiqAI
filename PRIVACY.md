# Rafiq AI Privacy Policy — Implementation Template

**Last updated:** 2026-10-07

This document is a product implementation template. Before Google Play publication, replace the developer/contact placeholders and obtain jurisdiction-specific legal review.

## Data we process

Rafiq AI may process:
- Email address and account credentials.
- Conversation titles and message content.
- Task titles, descriptions and optional due dates.
- Basic account preferences such as language.
- Technical request metadata needed for security, abuse prevention and reliability.

## Why we process it

- Authentication and account management.
- Synchronizing conversations/tasks across the user's devices.
- Providing AI responses requested by the user.
- Protecting the service from abuse.
- Diagnosing reliability and security incidents.

## AI providers

Conversation content may be transmitted from the Rafiq AI backend to the configured AI provider to generate responses. The exact provider, retention and processing terms must be disclosed in the final public policy before launch.

The Android application does not contain the AI provider API key.

## Security

- HTTPS is required for production API traffic.
- Passwords are hashed server-side.
- Access tokens are short-lived.
- Refresh tokens are opaque, rotated and stored hashed on the server.
- Android session secrets are protected using Android Keystore-backed encryption.
- Database ownership checks prevent one account from reading another account's resources.

## Retention and deletion

Users can delete their account from the application. The backend deletes the account and related PostgreSQL records through cascading relationships. Production operators must define and publish any legal/security retention exceptions before launch.

## Contact

Replace with the legal publisher name and privacy contact email before release.
