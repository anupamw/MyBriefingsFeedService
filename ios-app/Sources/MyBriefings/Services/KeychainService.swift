import Foundation
import Security

/// Secure storage service using iOS Keychain
class KeychainService {
    static let shared = KeychainService()
    
    private let service = "com.mybriefings.app"
    
    private init() {}
    
    // MARK: - Save
    func save(_ data: Data, for key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecValueData as String: data
        ]
        
        // Delete any existing item
        SecItemDelete(query as CFDictionary)
        
        // Add the new item
        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }
    
    func save(_ string: String, for key: String) -> Bool {
        guard let data = string.data(using: .utf8) else { return false }
        return save(data, for: key)
    }
    
    // MARK: - Retrieve
    func retrieve(for key: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        guard status == errSecSuccess else { return nil }
        return result as? Data
    }
    
    func retrieveString(for key: String) -> String? {
        guard let data = retrieve(for: key) else { return nil }
        return String(data: data, encoding: .utf8)
    }
    
    // MARK: - Delete
    func delete(for key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess
    }
    
    // MARK: - Clear All
    func clearAll() -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}

// MARK: - Token Storage Keys
extension KeychainService {
    private enum Keys {
        static let accessToken = "access_token"
        static let refreshToken = "refresh_token"
        static let tokenExpiry = "token_expiry"
    }
    
    // MARK: - Token Management
    func saveTokens(accessToken: String, refreshToken: String?, expiresIn: TimeInterval?) {
        _ = save(accessToken, for: Keys.accessToken)
        
        if let refreshToken = refreshToken {
            _ = save(refreshToken, for: Keys.refreshToken)
        }
        
        if let expiresIn = expiresIn {
            let expiryDate = Date().addingTimeInterval(expiresIn)
            let expiryString = ISO8601DateFormatter().string(from: expiryDate)
            _ = save(expiryString, for: Keys.tokenExpiry)
        }
    }
    
    func getAccessToken() -> String? {
        return retrieveString(for: Keys.accessToken)
    }
    
    func getRefreshToken() -> String? {
        return retrieveString(for: Keys.refreshToken)
    }
    
    func getTokenExpiry() -> Date? {
        guard let expiryString = retrieveString(for: Keys.tokenExpiry) else { return nil }
        return ISO8601DateFormatter().date(from: expiryString)
    }
    
    func isTokenExpired() -> Bool {
        guard let expiryDate = getTokenExpiry() else { return true }
        return Date() >= expiryDate.addingTimeInterval(-300) // 5 minutes buffer
    }
    
    func clearTokens() {
        _ = delete(for: Keys.accessToken)
        _ = delete(for: Keys.refreshToken)
        _ = delete(for: Keys.tokenExpiry)
    }
    
    func hasValidTokens() -> Bool {
        guard getAccessToken() != nil else { return false }
        return !isTokenExpired()
    }
}

