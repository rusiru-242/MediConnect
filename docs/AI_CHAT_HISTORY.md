# MediConnect AI Assistant

## Root causes

- The booking reply interpolated a nullable specialty filter, producing text such as “approved None.” Search also dropped the city filter after an empty result and supplied placeholder values for missing doctor fields.
- The intent classifier treated most turns in a booking state as booking requests. The agent then searched whenever it found an old specialty or city in the session. It had no separate action for asking about the profile of a doctor in the previous results.
- Flutter rendered doctor cards according to the latest booking state. A change in state could hide valid results, and earlier messages carried no doctor cards to restore.
- The assistant created a new booking session whenever it mounted. MongoDB already stored the transcript, but the session expired after 30 minutes and the app had no history list or route to reopen it.
- Stripe intent creation included the current second in its idempotency key. A retry after a lost response could generate a different key for the same payment attempt.

## Backend and storage

The patient JWT determines the owner of every conversation. The conversation routes return 404 for IDs outside that patient's history. Existing booking endpoints continue to resolve doctors and slots and require explicit patient confirmation before creating a hold.

| Method | Endpoint | Behavior |
| --- | --- | --- |
| POST | `/api/ai/conversations` | Starts a conversation or returns the patient's existing empty draft. An optional `initialMessage` starts and populates a new conversation. |
| GET | `/api/ai/conversations` | Lists conversation titles, previews, timestamps and booking states. Use `limit` and `offset` to page through newest activity first. |
| GET | `/api/ai/conversations/{id}/messages` | Returns messages in chronological order. Use `limit` and the returned `nextBefore` position to fetch older pages. |
| POST | `/api/ai/conversations/{id}/messages` | Saves the patient's message and the assistant's response together. Flutter sends a stable `requestId` for retries. |
| PATCH | `/api/ai/conversations/{id}` | Renames the conversation using a non-blank title of up to 100 characters. |
| DELETE | `/api/ai/conversations/{id}` | Permanently removes the conversation and its embedded transcript. Existing appointments, holds and payment records retain their normal lifecycle. |

The assistant reuses `booking_sessions`. Persistent documents contain the owner, title, state, timestamps, preview, booking context and transcript. Each message carries an ID, sender, timestamp, content and optional metadata. Doctor search and details messages include public profile fields for the cards. Active availability is queried when the patient selects a date.

- `idx_ai_conversation_history` indexes patient, persistence flag, activity time and document ID.
- `idx_ai_conversation_single_draft` is a partial unique index that allows one empty draft per patient.
- Persistent documents omit `expiresAt`. The existing TTL index still applies to legacy booking sessions. Legacy transcripts are subject to that original expiry and are outside the new history list.
- A MongoDB document update commits the conversation state and transcript together. Revision checks reject competing updates. A confirmation lease serializes booking confirmation with other conversation mutations.
- Flutter reopens the most recently active conversation when it mounts. Text turns are capped at 500 transcript entries per conversation to keep the embedded transcript bounded. English is the default; Sinhala and romanized Sinhala support depend on the recognized expression.

## Configuration

Use the existing backend configuration in `backend/.env`. `MONGODB_URI`, `DATABASE_NAME` and `JWT_SECRET` are required for authenticated persistent chat. Set `DATABASE_NAME=mediconnect_staging` for the normal staging database and use a separate database for integration tests.

For optional provider-backed search parsing, set the existing AI provider key and model values, such as `GEMINI_API_KEY` and `GEMINI_MODEL` or `OPENAI_API_KEY` and `OPENAI_MODEL`. `AI_TIMEOUT_SECONDS` controls the provider timeout. Chat has a local parsing fallback. Use test-mode `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` and `STRIPE_WEBHOOK_SECRET` for payment testing. The Android emulator can point to a local backend with `--dart-define=API_BASE_URL=http://10.0.2.2:8000`.

The staging profiles inspected used `hospitalOrClinic` and had no dedicated city value. For profiles like these, city filtering uses the location text stored in the clinic field. A dedicated `city` field is used when one exists.

## Manual verification

1. Start the backend and Flutter app against a test database with two active patients and an approved active doctor whose profile has a Colombo location and a future slot.
2. Sign in as the first patient, open **AI Assistant** and send **Find a doctor in Colombo**. Check the doctor's actual name, specialty or fallback, clinic and fee in the card.
3. Send **Doctorge details kiyanna**. If several doctors match, reply with a doctor's name or an ordinal such as **the second one**. Check that the assistant shows the chosen profile. Open **View Details** to verify the live profile.
4. Open **View Available Slots**, choose the date and check that the UI shows only unbooked slots. For a full booking test, select one slot and check the summary. Confirm the hold explicitly and exercise a declined and a successful payment using Stripe test mode. Verify the final appointment in **My Appointments**.
5. Tap **New Chat** and send **Hello**. Check that the new conversation starts with a greeting and has no previous doctor selection.
6. Open **Chat History** and return to the first conversation. Check that its messages and cards are restored. Rename it, restart Flutter, and open it again from History.
7. Sign in as the second patient and check that the first patient's chats are absent. An API request authenticated as the second patient for the first patient's conversation ID should return 404.
8. As the original patient, delete a disposable chat after confirming the prompt. Reload history and verify that the chat is gone.

## Changed files

- Backend entry point and APIs — `backend/app/main.py`, `backend/app/routes/ai_conversations.py`.
- Agent and search — `backend/app/agents/booking_agent.py`, `backend/app/agents/companion_intent.py`, `backend/app/agents/ai_provider.py`, `backend/app/services/doctor_service.py`, `backend/app/schemas/doctor.py`.
- Conversation state and payments — `backend/app/models/booking_session.py`, `backend/app/schemas/booking_session.py`, `backend/app/services/booking_session_service.py`, `backend/app/services/payment_service.py`.
- Flutter navigation and data — `mobile/lib/main.dart`, `mobile/lib/models/booking_session.dart`, `mobile/lib/models/doctor.dart`, `mobile/lib/services/ai_booking_service.dart`.
- Flutter screens — `mobile/lib/screens/patient/ai_care_assistant_screen.dart`, `mobile/lib/screens/patient/ai_chat_history_sheet.dart`, `mobile/lib/screens/patient/ai_booking_assistant_screen.dart`, `mobile/lib/screens/patient/doctor_detail_screen.dart`.
- Tests — `backend/tests/test_ai_booking_agent.py`, `backend/tests/test_payment.py`, `mobile/test/screens/ai_care_assistant_screen_test.dart`, `mobile/test/screens/ai_booking_assistant_screen_test.dart`.
