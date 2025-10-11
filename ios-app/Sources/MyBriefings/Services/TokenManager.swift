import Foundation

/// Manages authentication tokens with automatic refresh capabilities
class TokenManager: ObservableObject {
    static let shared = TokenManager()
    
    @Published var isAuthenticated = false
    
    private let keychain = KeychainService.shared
    private let refreshThreshold: TimeInterval = 300 // 5 minutes
    
    private init() {
        checkAuthenticationStatus()
    }
    
    // MARK: - Authentication Status
    private func checkAuthenticationStatus() {
        isAuthenticated = keychain.hasValidTokens()
    }
    
    // MARK: - Token Management
    func saveTokens(accessToken: String, refreshToken: String? = nil, expiresIn: TimeInterval? = nil) {
        keychain.saveTokens(
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresIn: expiresIn
        )
        
        DispatchQueue.main.async {
            self.isAuthenticated = true
        }
    }
    
    func getValidAccessToken() async -> String? {
        // Check if current token is valid
        if keychain.hasValidTokens() {
            return keychain.getAccessToken()
        }
        
        // Try to refresh the token if expired
        if await refreshTokenIfNeeded() {
            return keychain.getAccessToken()
        }
        
        // No valid token available
        return nil
    }
    
    func clearTokens() {
        keychain.clearTokens()
        DispatchQueue.main.async {
            self.isAuthenticated = false
        }
    }
    
    // MARK: - Token Refresh
    @discardableResult
    private func refreshTokenIfNeeded() async -> Bool {
        guard let refreshToken = keychain.getRefreshToken() else {
            // No refresh token available, user needs to login
            clearTokens()
            return false
        }
        
        do {
            let response = try await refreshAccessToken(refreshToken: refreshToken)
            
            // Save new tokens
            saveTokens(
                accessToken: response.access_token,
                refreshToken: response.refresh_token,
                expiresIn: response.expires_in
            )
            
            return true
        } catch {
            print("Token refresh failed: \(error)")
            clearTokens()
            return false
        }
    }
    
    private func refreshAccessToken(refreshToken: String) async throws -> RefreshTokenResponse {
        // This would typically call your backend's refresh endpoint
        // For now, we'll simulate the API call structure
        
        guard let url = URL(string: "https://mybriefings.org/auth/refresh") else {
            throw TokenError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let refreshRequest = RefreshTokenRequest(refresh_token: refreshToken)
        request.httpBody = try JSONEncoder().encode(refreshRequest)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw TokenError.invalidResponse
        }
        
        guard 200...299 ~= httpResponse.statusCode else {
            throw TokenError.refreshFailed(httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode(RefreshTokenResponse.self, from: data)
    }
}

// MARK: - Token Models
struct RefreshTokenRequest: Codable {
    let refresh_token: String
}

struct RefreshTokenResponse: Codable {
    let access_token: String
    let refresh_token: String?
    let expires_in: TimeInterval?
    let token_type: String
}

// MARK: - Token Errors
enum TokenError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case refreshFailed(Int)
    case noRefreshToken
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid refresh URL"
        case .invalidResponse:
            return "Invalid refresh response"
        case .refreshFailed(let code):
            return "Token refresh failed with code: \(code)"
        case .noRefreshToken:
            return "No refresh token available"
        }
    }
}

