use axum::{
    routing::{get, post},
    Router,
};
use std::net::SocketAddr;
use tower_http::cors::CorsLayer;

#[tokio::main]
async fn main() {
    // 1. Allow the Next.js frontend to communicate with this API
    let cors = CorsLayer::permissive();

    // 2. Define the application routes
    let app = Router::new()
        .route("/health", get(health_check))
        // We will build the upload handler next!
        // .route("/api/upload-ecg", post(handle_ecg_upload))
        .layer(cors);

    // 3. Bind the server to port 3000
    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    println!("🚀 Rust API Gateway running on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

// A simple health check to ensure the Rust server is alive
async fn health_check() -> &'static str {
    "Gateway is healthy and ready to route traffic!"
}