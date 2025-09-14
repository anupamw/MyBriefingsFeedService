import SwiftUI

@main
struct MyBriefingsApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @State private var username = ""
    @State private var password = ""
    @State private var isLoggedIn = false
    
    init() {
        print("🚀 MyBriefings App Started!")
    }
    
    var body: some View {
        if isLoggedIn {
            print("ContentView: Showing MainTabView (isLoggedIn = true)")
            return AnyView(MainTabView(isLoggedIn: $isLoggedIn))
        } else {
            print("ContentView: Showing LoginView (isLoggedIn = false)")
            return AnyView(NavigationView {
                LoginView(username: $username, password: $password, isLoggedIn: $isLoggedIn)
            })
        }
    }
}

struct LoginView: View {
    @Binding var username: String
    @Binding var password: String
    @Binding var isLoggedIn: Bool
    
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
                
                Button("Sign In") {
                    // For demo purposes, any username/password works
                    if !username.isEmpty && !password.isEmpty {
                        isLoggedIn = true
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 50)
                .background(Color.blue)
                .foregroundColor(.white)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .disabled(username.isEmpty || password.isEmpty)
            }
            .padding(.horizontal, 30)
            
            Spacer()
        }
        .padding()
        .navigationTitle("")
        .navigationBarHidden(true)
    }
}

struct MainTabView: View {
    @Binding var isLoggedIn: Bool
    
    var body: some View {
        NavigationView {
            TabView {
            FeedView()
                .tabItem {
                    Image(systemName: "newspaper")
                    Text("Feed")
                }
            
            CategoriesView()
                .tabItem {
                    Image(systemName: "folder")
                    Text("Categories")
                }
            
            SettingsView(isLoggedIn: $isLoggedIn)
                .tabItem {
                    Image(systemName: "gear")
                    Text("Settings")
                }
            }
        }
    }
}

struct FeedView: View {
    let sampleArticles = [
        FeedArticle(title: "Breaking: Major Tech Announcement", source: "TechNews", category: "Technology"),
        FeedArticle(title: "Global Markets Show Strong Growth", source: "FinancialTimes", category: "Finance"),
        FeedArticle(title: "Climate Summit Reaches New Agreement", source: "NewsAPI", category: "Environment"),
        FeedArticle(title: "AI Research Breakthrough Announced", source: "Perplexity", category: "Technology"),
        FeedArticle(title: "Sports Championship Finals Begin", source: "Reddit", category: "Sports")
    ]
    
    var body: some View {
        List(sampleArticles) { article in
            ArticleRow(article: article)
        }
        .navigationTitle("My Feed")
        .refreshable {
            // Pull to refresh
        }
    }
}

struct FeedArticle: Identifiable {
    let id = UUID()
    let title: String
    let source: String
    let category: String
}

struct ArticleRow: View {
    let article: FeedArticle
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(article.source)
                    .font(.caption)
                    .foregroundColor(.blue)
                    .fontWeight(.medium)
                
                Spacer()
                
                Text("2h ago")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Text(article.title)
                .font(.headline)
                .lineLimit(2)
            
            Text(article.category)
                .font(.caption)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.gray.opacity(0.2))
                .clipShape(Capsule())
        }
        .padding(.vertical, 4)
    }
}

struct CategoriesView: View {
    let categories = ["Technology", "Finance", "Environment", "Sports", "Politics", "Health"]
    
    var body: some View {
        List(categories, id: \.self) { category in
            HStack {
                Text(category)
                    .font(.headline)
                Spacer()
                Text("12 articles")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 4)
        }
        .navigationTitle("Categories")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button("Add") {
                    // Add new category
                }
            }
        }
    }
}

struct SettingsView: View {
    @Binding var isLoggedIn: Bool
    @State private var showingLogoutAlert = false
    
    var body: some View {
        List {
            Section("Profile") {
                HStack {
                    Image(systemName: "person.circle.fill")
                        .font(.title)
                        .foregroundColor(.blue)
                    
                    VStack(alignment: .leading) {
                        Text("Demo User")
                            .font(.headline)
                        Text("demo@mybriefings.com")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.vertical, 4)
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
            }
            
            Section {
                Button("Sign Out") {
                    print("🔴 DIRECT LOGOUT - Setting isLoggedIn to false")
                    isLoggedIn = false
                    print("🔴 isLoggedIn is now: \(isLoggedIn)")
                }
                .foregroundColor(.red)
            }
        }
        .navigationTitle("Settings")
        .alert("Sign Out", isPresented: $showingLogoutAlert) {
            Button("Cancel", role: .cancel) { 
                print("Logout cancelled")
            }
            Button("Sign Out", role: .destructive) {
                print("Logout confirmed - Setting isLoggedIn to false")
                isLoggedIn = false
                print("isLoggedIn is now: \(isLoggedIn)")
            }
        }
    }
}

#Preview {
    ContentView()
}
