//! 官方 worldstate 拉取（reqwest，gzip，UA，30s 超时，重试 1 次）

use std::time::Duration;

use reqwest::Client;
use serde_json::Value;

static CLIENT: std::sync::OnceLock<Client> = std::sync::OnceLock::new();

fn client() -> &'static Client {
    CLIENT.get_or_init(|| {
        Client::builder()
            .user_agent("warframe-api/0.1")
            .timeout(Duration::from_secs(30))
            .gzip(true)
            .build()
            .expect("reqwest client build")
    })
}

/// 拉取原始 JSON（gzip 自动解压）。失败返回可读错误。
pub async fn fetch_raw(url: &str) -> Result<Value, String> {
    let mut last_err = String::new();
    for attempt in 0..2 {
        match client().get(url).send().await {
            Ok(resp) => {
                if !resp.status().is_success() {
                    last_err = format!("upstream http {}", resp.status());
                } else {
                    let bytes = resp.bytes().await.map_err(|e| e.to_string())?;
                    return serde_json::from_slice(&bytes).map_err(|e| format!("json: {e}"));
                }
            }
            Err(e) => last_err = format!("{e}"),
        }
        tokio::time::sleep(Duration::from_secs(1)).await;
        let _ = attempt;
    }
    Err(last_err)
}
