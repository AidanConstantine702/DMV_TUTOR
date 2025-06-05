# DMV Tutor

This Streamlit app provides practice quizzes, flashcards, and a chat-based tutor for the South Carolina DMV permit test. It integrates with Supabase for storage and Stripe for payments.

## Configuration

Secrets are **not** stored in the repository. Set the following environment variables before running the app or provide them via `st.secrets`:

- `OPENAI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_PRICE_ID`
- `STRIPE_SUCCESS_URL`
- `STRIPE_CANCEL_URL`

Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and fill in your values when developing locally. Streamlit reads `secrets.toml` automatically when it is present. Make sure the `[supabase] anon_key` value is populated in this file or provided via the `SUPABASE_ANON_KEY` environment variable before running the app.

Install dependencies with `pip install -r requirements.txt` and start the app using `streamlit run app.py`.
