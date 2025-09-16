import SwiftUI
import Foundation

// MARK: - Environment Configuration
enum Environment {
    case development
    case production
    
    var baseURL: String {
        switch self {
        case .development:
            return "http://localhost:8000"
        case .production:
            return "http://64.227.134.87:30100"
        }
    }
    
    var displayName: String {
        switch self {
        case .development:
            return "Development (localhost:8000)"
        case .production:
            return "Production (64.227.134.87:30100)"
        }
    }
}

class AppConfig: ObservableObject {
    @Published var currentEnvironment: Environment
    
    init() {
        // Auto-detect environment based on build configuration
        #if DEBUG
        self.currentEnvironment = .development
        #else
        self.currentEnvironment = .production
        #endif
        
        // Allow manual override from UserDefaults
        if let savedEnv = UserDefaults.standard.string(forKey: "selected_environment") {
            if savedEnv == "production" {
                self.currentEnvironment = .production
            } else {
                self.currentEnvironment = .development
            }
        }
    }
    
    func switchEnvironment(to environment: Environment) {
        currentEnvironment = environment
        UserDefaults.standard.set(environment == .production ? "production" : "development", forKey: "selected_environment")
        
        // Clear auth token when switching environments
        UserDefaults.standard.removeObject(forKey: "auth_token")
        
        // Notify APIService to update
        NotificationCenter.default.post(name: .environmentChanged, object: environment)
    }
}

extension Notification.Name {
    static let environmentChanged = Notification.Name("environmentChanged")
}

// MARK: - API Models
struct LoginRequest: Codable {
    let username: String
    let password: String
}

struct LoginResponse: Codable {
    let access_token: String
    let token_type: String
}

struct User: Codable {
    let id: Int
    let username: String
    let email: String
    let created_at: String?
}

struct UserCategory: Codable {
    let id: Int
    let user_id: Int
    let category_name: String
    let short_summary: String?
    let subreddits: String?
    let twitter: String?
    let created_at: String?
}

struct UserCategoryCreate: Codable {
    let category_name: String
}

struct FeedItem: Codable {
    let id: Int
    let title: String?
    let summary: String?
    let content: String?
    let url: String?
    let source: String?
    let published_at: String?
    let created_at: String?
    let category: String?
    let short_summary: String?
}

struct AISummaryStatus: Codable {
    let user_id: Int
    let status: String
    let message: String
    let can_generate_summary: Bool
    let total_categories: Int?
    let total_feed_items: Int?
    let recent_feed_items: Int?
    let categories: [String]?
    let last_updated: String?
}

struct AISummary: Codable {
    let id: Int
    let summary_content: String
    let word_count: Int
    let max_words_requested: Int
    let categories_covered: [String]
    let total_feed_items_analyzed: Int
    let generated_at: String
    let source: String
}

struct AISummaryResponse: Codable {
    let user_id: Int
    let has_summary: Bool
    let message: String?
    let summary: AISummary?
}

struct AISummaryGenerateResponse: Codable {
    let message: String
    let summary_id: Int
    let user_id: Int
    let summary: String
    let word_count: Int
    let max_words_requested: Int
    let categories_covered: [String]
    let total_feed_items_analyzed: Int
    let generated_at: String
    let source: String
}

// MARK: - API Service
class APIService: ObservableObject {
    static let shared = APIService()
    private let session = URLSession.shared
    
    @Published var isAuthenticated = false
    private var appConfig = AppConfig()
    
    private var baseURL: String {
        return appConfig.currentEnvironment.baseURL
    }
    private var authToken: String? {
        get { UserDefaults.standard.string(forKey: "auth_token") }
        set { 
            UserDefaults.standard.set(newValue, forKey: "auth_token")
            isAuthenticated = newValue != nil
        }
    }
    
    init() {
        isAuthenticated = authToken != nil
        
        // Listen for environment changes
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(environmentChanged(_:)),
            name: .environmentChanged,
            object: nil
        )
    }
    
    @objc private func environmentChanged(_ notification: Notification) {
        if let newEnvironment = notification.object as? Environment {
            appConfig.currentEnvironment = newEnvironment
            // Force re-authentication when environment changes
            isAuthenticated = false
        }
    }
    
    private func makeRequest(endpoint: String, method: String = "GET", body: Data? = nil) async throws -> Data {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body = body {
            request.httpBody = body
        }
        
        let (data, response) = try await session.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        if httpResponse.statusCode == 401 {
            authToken = nil
            throw APIError.unauthorized
        }
        
        guard 200...299 ~= httpResponse.statusCode else {
            throw APIError.serverError(httpResponse.statusCode)
        }
        
        return data
    }
    
    // MARK: - Authentication
    func login(username: String, password: String) async throws -> LoginResponse {
        let request = LoginRequest(username: username, password: password)
        let data = try JSONEncoder().encode(request)
        
        let responseData = try await makeRequest(endpoint: "/auth/login", method: "POST", body: data)
        let response = try JSONDecoder().decode(LoginResponse.self, from: responseData)
        
        authToken = response.access_token
        return response
    }
    
    func logout() {
        authToken = nil
    }
    
    // MARK: - Categories
    func fetchCategories() async throws -> [UserCategory] {
        let data = try await makeRequest(endpoint: "/user/categories")
        return try JSONDecoder().decode([UserCategory].self, from: data)
    }
    
    func createCategory(name: String) async throws -> UserCategory {
        let request = UserCategoryCreate(category_name: name)
        let data = try JSONEncoder().encode(request)
        
        let responseData = try await makeRequest(endpoint: "/user/categories", method: "POST", body: data)
        return try JSONDecoder().decode(UserCategory.self, from: responseData)
    }
    
    func deleteCategory(id: Int) async throws {
        _ = try await makeRequest(endpoint: "/user/categories/\(id)", method: "DELETE")
    }
    
    // MARK: - Feed
    func fetchFeed(limit: Int = 30, offset: Int = 0, category: String? = nil) async throws -> [FeedItem] {
        var endpoint = "/feed?limit=\(limit)&offset=\(offset)"
        if let category = category {
            endpoint += "&category=\(category.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }
        
        let data = try await makeRequest(endpoint: endpoint)
        return try JSONDecoder().decode([FeedItem].self, from: data)
    }
    
    // MARK: - AI Summary
    func getAISummaryStatus() async throws -> AISummaryStatus {
        let data = try await makeRequest(endpoint: "/ai-summary/status")
        return try JSONDecoder().decode(AISummaryStatus.self, from: data)
    }
    
    func getLatestAISummary() async throws -> AISummaryResponse {
        let data = try await makeRequest(endpoint: "/ai-summary/latest")
        return try JSONDecoder().decode(AISummaryResponse.self, from: data)
    }
    
    func generateAISummary(maxWords: Int = 300) async throws -> AISummaryGenerateResponse {
        let endpoint = "/ai-summary/generate-and-store?max_words=\(maxWords)"
        let data = try await makeRequest(endpoint: endpoint, method: "POST")
        return try JSONDecoder().decode(AISummaryGenerateResponse.self, from: data)
    }
    
    // MARK: - Feed Ingestion
    func triggerFeedIngestion() async throws {
        _ = try await makeRequest(endpoint: "/api/ingestion/ingest/perplexity", method: "POST")
    }
    
    // MARK: - User Info
    func getCurrentUser() async throws -> User {
        let data = try await makeRequest(endpoint: "/auth/me")
        return try JSONDecoder().decode(User.self, from: data)
    }
}

// MARK: - API Errors
enum APIError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case unauthorized
    case serverError(Int)
    case networkError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .invalidResponse:
            return "Invalid response"
        case .unauthorized:
            return "Unauthorized - please login again"
        case .serverError(let code):
            return "Server error: \(code)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        }
    }
}

@main
struct MyBriefingsApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @StateObject private var apiService = APIService.shared
    @StateObject private var appConfig = AppConfig()
    @State private var userCategories: [UserCategory] = []
    
    var body: some View {
        if apiService.isAuthenticated {
            MainTabView(apiService: apiService, appConfig: appConfig, userCategories: $userCategories)
                .onAppear {
                    Task {
                        await loadCategories()
                    }
                }
        } else {
            NavigationView {
                LoginView(apiService: apiService, appConfig: appConfig)
            }
        }
    }
    
    private func loadCategories() async {
        do {
            userCategories = try await apiService.fetchCategories()
        } catch {
            print("Failed to load categories: \(error)")
        }
    }
}

struct LoginView: View {
    let apiService: APIService
    @ObservedObject var appConfig: AppConfig
    @State private var username = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showEnvironmentPicker = false
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "newspaper.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.blue)
            
            Text("My Briefings")
                .font(.largeTitle)
                .fontWeight(.bold)
            
            Text("Your personalized news feed")
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            VStack(spacing: 16) {
                TextField("Username", text: $username)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .autocapitalization(.none)
                
                SecureField("Password", text: $password)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                
                if let errorMessage = errorMessage {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .font(.caption)
                }
                
                Button("Sign In") {
                    Task {
                        await signIn()
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 50)
                .background(isLoading ? Color.gray : Color.blue)
                .foregroundColor(.white)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .disabled(username.isEmpty || password.isEmpty || isLoading)
                .overlay(
                    isLoading ? ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(0.8) : nil
                )
            }
            .padding(.horizontal, 30)
            
            // Discrete Environment Switcher
            VStack(spacing: 12) {
                Button(action: {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        showEnvironmentPicker.toggle()
                    }
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: "server.rack")
                            .font(.caption2)
                        Text("Environment: \(appConfig.currentEnvironment == .development ? "Dev" : "Prod")")
                            .font(.caption2)
                        Image(systemName: showEnvironmentPicker ? "chevron.up" : "chevron.down")
                            .font(.caption2)
                    }
                    .foregroundColor(.secondary)
                }
                
                if showEnvironmentPicker {
                    VStack(spacing: 8) {
                        Picker("Environment", selection: $appConfig.currentEnvironment) {
                            Text("Development (localhost:8000)").tag(Environment.development)
                            Text("Production (64.227.134.87:30100)").tag(Environment.production)
                        }
                        .pickerStyle(SegmentedPickerStyle())
                        .onChange(of: appConfig.currentEnvironment) { newEnvironment in
                            appConfig.switchEnvironment(to: newEnvironment)
                            errorMessage = nil // Clear any previous errors
                        }
                        
                        Text("Current: \(appConfig.currentEnvironment.displayName)")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .transition(.opacity.combined(with: .scale(scale: 0.95)))
                }
            }
            .padding(.horizontal, 30)
            
            Spacer()
        }
        .padding()
        .navigationTitle("")
        .navigationBarHidden(true)
    }
    
    private func signIn() async {
        isLoading = true
        errorMessage = nil
        
        do {
            _ = try await apiService.login(username: username, password: password)
            // APIService will automatically update isAuthenticated
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
}

struct MainTabView: View {
    let apiService: APIService
    @ObservedObject var appConfig: AppConfig
    @Binding var userCategories: [UserCategory]
    
    var body: some View {
        TabView {
            NavigationView {
                FeedView(apiService: apiService, userCategories: userCategories)
            }
            .tabItem {
                Image(systemName: "newspaper")
                Text("Feed")
            }
            
            NavigationView {
                CategoriesView(apiService: apiService, userCategories: $userCategories)
            }
            .tabItem {
                Image(systemName: "folder")
                Text("Categories")
            }
            
            NavigationView {
                AISummaryView(apiService: apiService)
            }
            .tabItem {
                Image(systemName: "brain")
                Text("AI Summary")
            }
            
            NavigationView {
                SettingsView(apiService: apiService, appConfig: appConfig)
            }
            .tabItem {
                Image(systemName: "gear")
                Text("Settings")
            }
        }
    }
}

struct FeedView: View {
    let apiService: APIService
    let userCategories: [UserCategory]
    @State private var feedItems: [FeedItem] = []
    @State private var isLoading = false
    @State private var isIngesting = false
    @State private var errorMessage: String?
    @State private var showingRefreshOptions = false
    
    var body: some View {
        List {
            if let errorMessage = errorMessage {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.caption)
            }
            
            ForEach(feedItems, id: \.id) { item in
                ArticleRow(feedItem: item)
            }
        }
        .navigationTitle("My Feed")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    Button("Refresh Feed", action: {
                        Task {
                            await loadFeed()
                        }
                    })
                    
                    Button("Get Fresh Data", action: {
                        Task {
                            await refreshWithIngestion()
                        }
                    })
                } label: {
                    if isLoading || isIngesting {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle())
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "arrow.clockwise")
                    }
                }
                .disabled(isLoading || isIngesting)
            }
        }
        .refreshable {
            await loadFeed()
        }
        .onAppear {
            Task {
                await loadFeed()
            }
        }
        .overlay(
            Group {
                if isLoading && feedItems.isEmpty {
                    ProgressView("Loading feed...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .background(Color(.systemBackground))
                } else if isIngesting {
                    VStack(spacing: 8) {
                        ProgressView()
                        Text("Getting fresh data...")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color(.systemBackground))
                }
            }
        )
    }
    
    private func loadFeed() async {
        isLoading = true
        errorMessage = nil
        
        do {
            feedItems = try await apiService.fetchFeed()
        } catch {
            errorMessage = "Failed to load feed: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    private func refreshWithIngestion() async {
        isIngesting = true
        errorMessage = nil
        
        do {
            // First trigger fresh data ingestion
            try await apiService.triggerFeedIngestion()
            
            // Wait a moment for ingestion to process
            try await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
            
            // Then refresh the feed
            feedItems = try await apiService.fetchFeed()
        } catch {
            errorMessage = "Failed to get fresh data: \(error.localizedDescription)"
        }
        
        isIngesting = false
    }
}

struct ArticleRow: View {
    let feedItem: FeedItem
    @State private var isExpanded = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header
            HStack {
                Text(feedItem.source ?? "Unknown")
                    .font(.caption)
                    .foregroundColor(.blue)
                    .fontWeight(.medium)
                
                Spacer()
                
                Text(timeAgo(from: feedItem.published_at))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Title
            Text(feedItem.title ?? "No Title")
                .font(.headline)
                .lineLimit(isExpanded ? nil : 2)
            
            // Summary
            if let summary = feedItem.summary, !summary.isEmpty {
                Text(summary)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(isExpanded ? nil : 3)
            }
            
            // Expanded content
            if isExpanded {
                VStack(alignment: .leading, spacing: 12) {
                    Divider()
                    
                    // Full content if available
                    if let content = feedItem.content, !content.isEmpty, content != feedItem.summary {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Full Article")
                                .font(.caption)
                                .fontWeight(.medium)
                                .foregroundColor(.secondary)
                            
                            Text(content)
                                .font(.body)
                                .lineSpacing(2)
                        }
                    }
                    
                    // Article details
                    VStack(alignment: .leading, spacing: 4) {
                        if let publishedAt = feedItem.published_at {
                            HStack {
                                Image(systemName: "calendar")
                                    .foregroundColor(.secondary)
                                    .font(.caption)
                                Text("Published: \(formatDate(publishedAt))")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        if let url = feedItem.url, !url.isEmpty {
                            HStack {
                                Image(systemName: "link")
                                    .foregroundColor(.secondary)
                                    .font(.caption)
                                Link("Read Original Article", destination: URL(string: url) ?? URL(string: "https://example.com")!)
                                    .font(.caption)
                            }
                        }
                    }
                }
            }
            
            // Category and expand button
            HStack {
                if let category = feedItem.category ?? feedItem.short_summary {
                    Text(category)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.gray.opacity(0.2))
                        .clipShape(Capsule())
                }
                
                Spacer()
                
                Button(action: {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        isExpanded.toggle()
                    }
                }) {
                    HStack(spacing: 4) {
                        Text(isExpanded ? "Show Less" : "Show More")
                            .font(.caption)
                        Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                            .font(.caption)
                    }
                    .foregroundColor(.blue)
                }
            }
        }
        .padding(.vertical, 4)
        .animation(.easeInOut(duration: 0.3), value: isExpanded)
    }
    
    private func timeAgo(from dateString: String?) -> String {
        guard let dateString = dateString,
              let date = ISO8601DateFormatter().date(from: dateString) else {
            return "Unknown"
        }
        
        let now = Date()
        let timeInterval = now.timeIntervalSince(date)
        
        if timeInterval < 3600 {
            let minutes = Int(timeInterval / 60)
            return "\(minutes)m ago"
        } else if timeInterval < 86400 {
            let hours = Int(timeInterval / 3600)
            return "\(hours)h ago"
        } else {
            let days = Int(timeInterval / 86400)
            return "\(days)d ago"
        }
    }
    
    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: dateString) else {
            return dateString
        }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        return displayFormatter.string(from: date)
    }
}

struct CategoriesView: View {
    let apiService: APIService
    @Binding var userCategories: [UserCategory]
    @State private var showingAddAlert = false
    @State private var newCategoryName = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    var body: some View {
        List {
            if let errorMessage = errorMessage {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.caption)
            }
            
            ForEach(userCategories, id: \.id) { category in
                NavigationLink(destination: CategoryFeedView(apiService: apiService, category: category)) {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(category.category_name)
                                .font(.headline)
                                .foregroundColor(.primary)
                            
                            if let shortSummary = category.short_summary {
                                Text(shortSummary)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        Spacer()
                        
                        Text("Tap to view")
                            .font(.caption)
                            .foregroundColor(.blue)
                    }
                    .padding(.vertical, 4)
                }
            }
            .onDelete(perform: deleteCategories)
        }
        .navigationTitle("Categories")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Add") {
                    showingAddAlert = true
                }
                .disabled(isLoading)
            }
            
            ToolbarItem(placement: .navigationBarLeading) {
                EditButton()
            }
        }
        .alert("Add Category", isPresented: $showingAddAlert) {
            TextField("Category name", text: $newCategoryName)
            Button("Cancel", role: .cancel) {
                newCategoryName = ""
            }
            Button("Add") {
                Task {
                    await addCategory()
                }
            }
        } message: {
            Text("Enter a name for the new category")
        }
        .refreshable {
            await loadCategories()
        }
    }
    
    private func addCategory() async {
        guard !newCategoryName.isEmpty else { return }
        
        isLoading = true
        errorMessage = nil
        
        do {
            let newCategory = try await apiService.createCategory(name: newCategoryName)
            userCategories.append(newCategory)
            newCategoryName = ""
        } catch {
            errorMessage = "Failed to add category: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    private func loadCategories() async {
        isLoading = true
        errorMessage = nil
        
        do {
            userCategories = try await apiService.fetchCategories()
        } catch {
            errorMessage = "Failed to load categories: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    private func deleteCategories(at offsets: IndexSet) {
        // Get categories to delete before modifying the array
        let categoriesToDelete = offsets.map { userCategories[$0] }
        
        Task {
            for category in categoriesToDelete {
                do {
                    try await apiService.deleteCategory(id: category.id)
                    await MainActor.run {
                        if let index = userCategories.firstIndex(where: { $0.id == category.id }) {
                            userCategories.remove(at: index)
                        }
                    }
                } catch {
                    await MainActor.run {
                        errorMessage = "Failed to delete \(category.category_name): \(error.localizedDescription)"
                    }
                }
            }
        }
    }
}

struct CategoryFeedView: View {
    let apiService: APIService
    let category: UserCategory
    @State private var feedItems: [FeedItem] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    var body: some View {
        List {
            if let errorMessage = errorMessage {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.caption)
            }
            
            ForEach(feedItems, id: \.id) { item in
                ArticleRow(feedItem: item)
            }
        }
        .navigationTitle(category.short_summary ?? category.category_name)
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: {
                    Task {
                        await loadCategoryFeed()
                    }
                }) {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle())
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "arrow.clockwise")
                    }
                }
                .disabled(isLoading)
            }
        }
        .refreshable {
            await loadCategoryFeed()
        }
        .onAppear {
            Task {
                await loadCategoryFeed()
            }
        }
        .overlay(
            isLoading && feedItems.isEmpty ? ProgressView("Loading \(category.short_summary ?? category.category_name)...")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(.systemBackground)) : nil
        )
    }
    
    private func loadCategoryFeed() async {
        isLoading = true
        errorMessage = nil
        
        do {
            // Use the category name or short summary to filter
            let categoryFilter = category.short_summary ?? category.category_name
            feedItems = try await apiService.fetchFeed(category: categoryFilter)
        } catch {
            errorMessage = "Failed to load category feed: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
}

struct AISummaryView: View {
    let apiService: APIService
    @State private var summaryResponse: AISummaryResponse?
    @State private var summaryStatus: AISummaryStatus?
    @State private var isGenerating = false
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var maxWords = 300
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Header
                VStack(alignment: .leading, spacing: 8) {
                    Text("Get an AI-powered summary of your personalized feed")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal)
                
                // Error Message
                if let errorMessage = errorMessage {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .font(.caption)
                        .padding(.horizontal)
                }
                
                // Status and Generate Summary Section (side by side)
                HStack(alignment: .top, spacing: 16) {
                    // Status Section
                    if let status = summaryStatus {
                        StatusCard(status: status)
                            .frame(maxWidth: .infinity)
                    }
                    
                    // Generate Summary Section (compact)
                    CompactGenerateSummaryCard(
                        maxWords: $maxWords,
                        isGenerating: isGenerating,
                        canGenerate: summaryStatus?.can_generate_summary ?? false,
                        onGenerate: {
                            Task {
                                await generateSummary()
                            }
                        }
                    )
                    .frame(maxWidth: .infinity)
                }
                .padding(.horizontal)
                
                // Latest Summary Section
                if let response = summaryResponse, response.has_summary, let summary = response.summary {
                    SummaryDisplayCard(summary: summary)
                        .padding(.horizontal)
                } else if summaryResponse?.has_summary == false {
                    NoSummaryCard()
                        .padding(.horizontal)
                }
                
                Spacer()
            }
        }
        .navigationTitle("AI Summary")
        .refreshable {
            await loadData()
        }
        .onAppear {
            Task {
                await loadData()
            }
        }
    }
    
    private func loadData() async {
        isLoading = true
        errorMessage = nil
        
        async let statusTask = loadStatus()
        async let summaryTask = loadLatestSummary()
        
        await statusTask
        await summaryTask
        
        isLoading = false
    }
    
    private func loadStatus() async {
        do {
            summaryStatus = try await apiService.getAISummaryStatus()
        } catch {
            errorMessage = "Failed to load status: \(error.localizedDescription)"
        }
    }
    
    private func loadLatestSummary() async {
        do {
            summaryResponse = try await apiService.getLatestAISummary()
        } catch {
            errorMessage = "Failed to load summary: \(error.localizedDescription)"
        }
    }
    
    private func generateSummary() async {
        isGenerating = true
        errorMessage = nil
        
        do {
            let result = try await apiService.generateAISummary(maxWords: maxWords)
            
            // Create a summary response from the generate response
            let summary = AISummary(
                id: result.summary_id,
                summary_content: result.summary,
                word_count: result.word_count,
                max_words_requested: result.max_words_requested,
                categories_covered: result.categories_covered,
                total_feed_items_analyzed: result.total_feed_items_analyzed,
                generated_at: result.generated_at,
                source: result.source
            )
            
            summaryResponse = AISummaryResponse(
                user_id: result.user_id,
                has_summary: true,
                message: nil,
                summary: summary
            )
        } catch {
            errorMessage = "Failed to generate summary: \(error.localizedDescription)"
        }
        
        isGenerating = false
    }
}

struct StatusCard: View {
    let status: AISummaryStatus
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: statusIcon)
                    .foregroundColor(statusColor)
                Text("Status")
                    .font(.headline)
            }
            
            Text(status.message)
                .font(.subheadline)
                .foregroundColor(.secondary)
            
            if let categories = status.categories, !categories.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Categories: \(categories.count)")
                        .font(.caption)
                        .fontWeight(.medium)
                    
                    Text("Feed Items: \(status.total_feed_items ?? 0)")
                        .font(.caption)
                        .fontWeight(.medium)
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
    
    private var statusIcon: String {
        switch status.status {
        case "ready": return "checkmark.circle.fill"
        case "no_categories": return "exclamationmark.circle.fill"
        case "no_feed_items": return "doc.circle.fill"
        default: return "info.circle.fill"
        }
    }
    
    private var statusColor: Color {
        switch status.status {
        case "ready": return .green
        case "no_categories", "no_feed_items": return .orange
        default: return .blue
        }
    }
}

struct GenerateSummaryCard: View {
    @Binding var maxWords: Int
    let isGenerating: Bool
    let canGenerate: Bool
    let onGenerate: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Generate New Summary")
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Summary Length")
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                HStack {
                    Text("Words: \(maxWords)")
                        .font(.caption)
                    
                    Spacer()
                    
                    Slider(value: Binding(
                        get: { Double(maxWords) },
                        set: { maxWords = Int($0) }
                    ), in: 100...1000, step: 50)
                }
            }
            
            Button("Generate AI Summary") {
                onGenerate()
            }
            .frame(maxWidth: .infinity)
            .frame(height: 50)
            .background(canGenerate && !isGenerating ? Color.blue : Color.gray)
            .foregroundColor(.white)
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .disabled(!canGenerate || isGenerating)
            .overlay(
                isGenerating ? ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    .scaleEffect(0.8) : nil
            )
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

struct CompactGenerateSummaryCard: View {
    @Binding var maxWords: Int
    let isGenerating: Bool
    let canGenerate: Bool
    let onGenerate: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Generate")
                .font(.headline)
            
            VStack(alignment: .leading, spacing: 6) {
                Text("\(maxWords) words")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Slider(value: Binding(
                    get: { Double(maxWords) },
                    set: { maxWords = Int($0) }
                ), in: 100...1000, step: 50)
                .accentColor(.blue)
            }
            
            Button("Generate") {
                onGenerate()
            }
            .frame(maxWidth: .infinity)
            .frame(height: 40)
            .background(canGenerate && !isGenerating ? Color.blue : Color.gray)
            .foregroundColor(.white)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .disabled(!canGenerate || isGenerating)
            .overlay(
                isGenerating ? ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    .scaleEffect(0.7) : nil
            )
        }
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

struct SummaryDisplayCard: View {
    let summary: AISummary
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Latest Summary")
                    .font(.headline)
                
                Spacer()
                
                Text(timeAgo(from: summary.generated_at))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Summary metadata
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(summary.word_count) words")
                        .font(.caption)
                        .fontWeight(.medium)
                    
                    Text("\(summary.total_feed_items_analyzed) articles")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(summary.categories_covered.count) categories")
                        .font(.caption)
                        .fontWeight(.medium)
                    
                    Text(summary.source)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Divider()
            
            // Summary content
            Text(summary.summary_content)
                .font(.body)
                .lineSpacing(4)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
    
    private func timeAgo(from dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: dateString) else {
            return "Unknown"
        }
        
        let now = Date()
        let timeInterval = now.timeIntervalSince(date)
        
        if timeInterval < 3600 {
            let minutes = Int(timeInterval / 60)
            return "\(minutes)m ago"
        } else if timeInterval < 86400 {
            let hours = Int(timeInterval / 3600)
            return "\(hours)h ago"
        } else {
            let days = Int(timeInterval / 86400)
            return "\(days)d ago"
        }
    }
}

struct NoSummaryCard: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "doc.text.magnifyingglass")
                .font(.system(size: 50))
                .foregroundColor(.gray)
            
            Text("No Summary Available")
                .font(.headline)
                .foregroundColor(.secondary)
            
            Text("Generate your first AI summary to see personalized insights from your feed")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

struct SettingsView: View {
    let apiService: APIService
    @ObservedObject var appConfig: AppConfig
    @State private var showingLogoutAlert = false
    @State private var currentUser: User?
    @State private var isLoadingUser = false
    
    var body: some View {
        List {
            Section("Profile") {
                HStack {
                    Image(systemName: "person.circle.fill")
                        .font(.title)
                        .foregroundColor(.blue)
                    
                    VStack(alignment: .leading) {
                        if let user = currentUser {
                            Text(user.username)
                                .font(.headline)
                            Text(user.email)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        } else if isLoadingUser {
                            Text("Loading...")
                                .font(.headline)
                                .foregroundColor(.secondary)
                        } else {
                            Text("Authenticated User")
                                .font(.headline)
                            Text("Connected to My Briefings")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.vertical, 4)
            }
            
            Section("Environment") {
                HStack {
                    Image(systemName: "server.rack")
                        .foregroundColor(.blue)
                    Text("Backend")
                    Spacer()
                    Text(appConfig.currentEnvironment.displayName)
                        .foregroundColor(.secondary)
                        .font(.caption)
                }
                
                HStack {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .foregroundColor(.orange)
                    Text("Switch Environment")
                    Spacer()
                    
                    Picker("Environment", selection: $appConfig.currentEnvironment) {
                        Text("Development").tag(Environment.development)
                        Text("Production").tag(Environment.production)
                    }
                    .pickerStyle(SegmentedPickerStyle())
                    .frame(width: 180)
                }
                .onChange(of: appConfig.currentEnvironment) { newEnvironment in
                    appConfig.switchEnvironment(to: newEnvironment)
                }
            }
            
            Section("App") {
                HStack {
                    Image(systemName: "info.circle")
                        .foregroundColor(.blue)
                    Text("Version")
                    Spacer()
                    Text("1.0.0")
                        .foregroundColor(.secondary)
                }
                
                HStack {
                    Image(systemName: "server.rack")
                        .foregroundColor(.blue)
                    Text("Backend")
                    Spacer()
                    Text("localhost:8000")
                        .foregroundColor(.secondary)
                        .font(.caption)
                }
            }
            
            Section {
                Button("Sign Out") {
                    showingLogoutAlert = true
                }
                .foregroundColor(.red)
            }
        }
        .navigationTitle("Settings")
        .alert("Sign Out", isPresented: $showingLogoutAlert) {
            Button("Cancel", role: .cancel) { }
            Button("Sign Out", role: .destructive) {
                apiService.logout()
            }
        }
        .onAppear {
            Task {
                await loadCurrentUser()
            }
        }
    }
    
    private func loadCurrentUser() async {
        isLoadingUser = true
        
        do {
            currentUser = try await apiService.getCurrentUser()
        } catch {
            print("Failed to load current user: \(error)")
            // Keep currentUser as nil to show fallback text
        }
        
        isLoadingUser = false
    }
}

#Preview {
    ContentView()
}

