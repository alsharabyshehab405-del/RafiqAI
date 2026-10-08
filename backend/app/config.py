from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "production"
    database_url: str
    jwt_secret: str
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    ai_base_url: str
    ai_api_key: str
    ai_model: str = "gpt-4.1-mini"
    ai_pro_model: str = "gpt-4.1-mini"
    ai_premium_model: str = "gpt-4.1-mini"
    ai_fallback_base_url: str = ""
    ai_fallback_api_key: str = ""
    ai_fallback_model: str = ""
    ai_provider_type: str = "openai_compatible"
    ai_pro_provider_type: str = "openai_compatible"
    ai_premium_provider_type: str = "openai_compatible"
    ai_anthropic_base_url: str = "https://api.anthropic.com"
    ai_anthropic_api_key: str = ""
    ai_gemini_base_url: str = "https://generativelanguage.googleapis.com"
    ai_gemini_api_key: str = ""
    qdrant_timeout_seconds: int = 15
    embedding_provider_type: str = "openai_compatible"
    ai_timeout_seconds: int = 90
    ai_max_context_messages: int = 40
    ai_context_tokens: int = 16000
    ai_max_tool_calls: int = 12
    ai_max_agent_seconds: int = 90
    ai_summary_enabled: bool = True
    ai_prompt_cache_enabled: bool = False
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    ai_max_context_chars: int = 50000
    ai_summary_threshold_chars: int = 30000
    ai_input_cost_per_1k: float = 0.0
    ai_output_cost_per_1k: float = 0.0
    cors_origins: str = ""
    rate_limit_per_minute: int = 60
    rate_limit_storage_uri: str = "memory://"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    max_input_chars: int = 12000
    max_file_bytes: int = 15728640
    max_file_uncompressed_bytes: int = 100000000
    log_level: str = "INFO"
    sentry_dsn: str = ""
    service_name: str = "rafiq-api"
    web_search_base_url: str = ""
    web_search_api_key: str = ""
    web_search_timeout_seconds: int = 15
    s3_endpoint_url: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    clamav_url: str = ""
    google_play_package_name: str = "com.rafiqai.app"
    google_play_service_account_json: str = ""
    firebase_service_account_json: str = ""
    pro_product_ids: str = "rafiq_pro_monthly,rafiq_pro_yearly"
    premium_product_ids: str = "rafiq_premium_monthly,rafiq_premium_yearly"
    product_prices_usd: str = "rafiq_pro_monthly=4.99,rafiq_pro_yearly=49.99,rafiq_premium_monthly=9.99,rafiq_premium_yearly=99.99"
    analytics_enabled: bool = True
    memory_enabled_by_default: bool = False
    data_retention_days: int = 365
    admin_emails: str = ""
    admin_bootstrap_token: str = ""
    fcm_enabled: bool = True
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_prefix: str = "rafiq"
    automation_poll_seconds: int = 30
    browser_allowed_domains: str = ""
    admin_session_max_minutes: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
