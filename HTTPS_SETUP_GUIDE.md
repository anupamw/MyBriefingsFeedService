# HTTPS Setup Guide for k3s Droplet

## Overview
Guide to switch from HTTP to HTTPS on your k3s droplet using Traefik and Let's Encrypt.

## Getting a Free Domain Name (Required for HTTPS)

Since you're currently using an IP address (`64.227.134.87`), you'll need a domain name for proper HTTPS setup. Here are your options:

### Option A: Free Cloudflare Domain (Recommended - $0/year)

Cloudflare offers free domain registration for certain TLDs:

#### 1. Sign up for Cloudflare
- Go to [cloudflare.com](https://cloudflare.com)
- Create a free account

#### 2. Register a free domain
- In Cloudflare dashboard, click "Add a Site"
- Choose "Register a new domain"
- Select from free TLDs:
  - `.tk` (Tokelau)
  - `.ml` (Mali) 
  - `.ga` (Gabon)
  - `.cf` (Central African Republic)
  - `.gq` (Equatorial Guinea)
- Examples: `mybriefings.tk`, `mybriefings.ml`, `mybriefings.cf`

#### 3. Point domain to your droplet
- In Cloudflare DNS settings, add an A record:
  ```
  Type: A
  Name: @ (or your chosen domain)
  Content: 64.227.134.87
  Proxy status: Proxied (orange cloud)
  ```

#### 4. Benefits of this approach:
- ✅ **Completely free** - $0/year
- ✅ **Free SSL certificate** included
- ✅ **Free CDN** and DDoS protection
- ✅ **Professional domain name**
- ✅ **No technical setup** required

### Option B: Paid Domain ($10-15/year)
- Register from any provider (Namecheap, GoDaddy, etc.)
- Use `.com`, `.net`, `.org` or other popular TLDs
- Then use Cloudflare's free services on top

### Option C: Self-Signed Certificate (Not Recommended)
- Works with IP addresses
- Causes browser security warnings
- Not suitable for production

**Recommendation:** Use Option A (free Cloudflare domain) for the most cost-effective solution.

## Option 1: Using k3s Built-in Traefik (Recommended)

### Overview
This option uses your existing k3s cluster's built-in Traefik load balancer combined with cert-manager to automatically obtain and manage SSL certificates from Let's Encrypt. The process involves installing cert-manager into your cluster, configuring it to communicate with Let's Encrypt's servers, and updating your ingress configuration to request TLS certificates for your domain. Once set up, cert-manager automatically handles certificate renewal, and Traefik serves your applications over HTTPS. This approach gives you full control over the SSL setup within your Kubernetes cluster and doesn't depend on external services, but requires you to have a domain name pointing to your droplet's IP address.

### Prerequisites
1. **Domain name** (e.g., `yourdomain.com`)
2. **DNS pointing to your droplet**: `yourdomain.com → 64.227.134.87`

### Getting a Domain Name Pointed to Your Droplet
Since you don't have a domain name yet, you'll need to register one first. You can get a domain from registrars like Namecheap, GoDaddy, or others (typically $10-15/year for .com domains). Once you have a domain, you go into your registrar's DNS management panel and create an "A record" that points your domain to your droplet's IP address (64.227.134.87). For example, if you bought "mybriefings.com", you'd create an A record where the hostname is "@" (representing the root domain) and the value is "64.227.134.87". DNS propagation can take a few hours to 48 hours to fully spread worldwide.

### Steps

#### 1. Install cert-manager
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

#### 2. Create ClusterIssuer for Let's Encrypt
Create file: `cluster-issuer.yaml`
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: traefik
```

Apply:
```bash
kubectl apply -f cluster-issuer.yaml
```

#### 3. Update your ingress configuration
Create file: `ingress-https.yaml`
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-briefings-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
spec:
  tls:
  - hosts:
    - yourdomain.com
    secretName: my-briefings-tls
  rules:
  - host: yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-briefings-app
            port:
              number: 8000
      - path: /ingestion
        pathType: Prefix
        backend:
          service:
            name: my-briefings-ingestion
            port:
              number: 8000
```

Apply:
```bash
kubectl apply -f ingress-https.yaml
```

#### 4. Update your application code
Replace hardcoded HTTP URLs with HTTPS:

**In main.py (signup endpoint):**
```python
# Change from:
"http://64.227.134.87:30101/ingest/perplexity"

# To:
"https://yourdomain.com/ingestion/ingest/perplexity"
```

**In frontend JavaScript:**
```javascript
// Change from:
"http://64.227.134.87:30101"

// To:
"https://yourdomain.com/ingestion"
```

## Option 2: Using Cloudflare (Alternative - FREE)

### Overview
This option leverages Cloudflare's free tier to handle SSL termination completely outside of your infrastructure. You point your domain's DNS to Cloudflare's servers, which then proxy requests to your droplet while automatically providing SSL certificates, CDN caching, and DDoS protection. Your k3s cluster continues running HTTP internally, but users see HTTPS through Cloudflare's proxy. This is simpler because you don't need to manage certificates, install additional software, or modify your Kubernetes configuration - Cloudflare handles all the complexity. The trade-off is that you're dependent on Cloudflare's service, but you gain performance benefits through their global CDN and additional security features at no cost.

### Cloudflare Free Tier Benefits:
- ✅ **Free SSL certificates** (automatic)
- ✅ **Free CDN** (faster loading)
- ✅ **Free DDoS protection**
- ✅ **Free DNS management**
- ✅ **No bandwidth limits** for most use cases
- ✅ **Cost:** $0/month

### How Cloudflare Works:
1. **Your domain** → **Cloudflare** → **Your droplet**
2. **Cloudflare handles SSL** (visitors see HTTPS)
3. **Cloudflare communicates with your droplet** (HTTP internally)

### Getting Started with Cloudflare (No Domain Required Initially)
Interestingly, Cloudflare can actually solve both problems for you. As mentioned in the HTTPS guide, Cloudflare offers **free domain registration** for certain country-code TLDs like .tk, .ml, .ga, .cf, and .gq. You can sign up for Cloudflare, register a free domain like "mybriefings.tk" directly through them, and they automatically handle the DNS setup. If you prefer a traditional domain (.com, .net), you'd first register it elsewhere, then add it to Cloudflare and change your domain registrar's nameservers to the ones Cloudflare provides (they'll give you specific ones like "nina.ns.cloudflare.com"). Either way, you then add an A record in Cloudflare's DNS panel pointing to 64.227.134.87 with the "Proxied" option enabled (orange cloud icon).

### Setup Steps:

#### 1. Sign up for Cloudflare (Free)
- Go to [cloudflare.com](https://cloudflare.com)
- Add your domain
- Cloudflare provides DNS servers

#### 2. Update your domain's DNS
Change your domain's nameservers to Cloudflare's:
```
Replace your current nameservers with:
- nina.ns.cloudflare.com
- rick.ns.cloudflare.com
```

#### 3. Add DNS record in Cloudflare
```
Type: A
Name: @ (or yourdomain.com)
Content: 64.227.134.87
Proxy status: Proxied (orange cloud) ← This is key!
```

#### 4. Configure SSL/TLS in Cloudflare
- Go to SSL/TLS settings
- Set to "Full" or "Full (strict)" mode
- Enable "Always Use HTTPS"

### What Changes on Your Droplet:

#### Option A: Keep HTTP (Recommended)
- **No changes needed** to your k3s setup
- Cloudflare handles SSL termination
- Your services continue running on HTTP internally

#### Option B: Force HTTPS (Optional)
- Update your ingress to redirect HTTP → HTTPS
- Add security headers

### What Changes in Your Code:

#### 1. Update Frontend API Calls
```javascript
// Change from:
"http://64.227.134.87:30101"

// To:
"https://yourdomain.com/ingestion"
```

#### 2. Update Backend Signup Code
```python
# In main.py signup endpoint, change from:
"http://64.227.134.87:30101/ingest/perplexity"

# To:
"https://yourdomain.com/ingestion/ingest/perplexity"
```

#### 3. Update CORS (if needed)
```python
# In your FastAPI apps, update CORS origins:
allow_origins=["https://yourdomain.com"]
```

### Cloudflare Dashboard Settings:

#### SSL/TLS Settings:
- **Encryption mode:** Full
- **Always Use HTTPS:** On
- **Minimum TLS Version:** 1.2

#### Page Rules (Optional):
- Create rule: `yourdomain.com/*`
- Settings: "Always Use HTTPS"

#### Security Settings:
- **Security Level:** Medium
- **Browser Integrity Check:** On
- **Challenge Passage:** 30 minutes

#### Performance Settings:
- **Auto Minify:** JavaScript, CSS, HTML
- **Brotli:** On
- **Rocket Loader:** On

#### Caching Settings:
- **Cache Level:** Standard
- **Browser Cache TTL:** 4 hours

### Benefits of Cloudflare Approach:

#### ✅ Pros:
- **Zero certificate management** (Cloudflare handles it)
- **Better performance** (CDN caching)
- **DDoS protection** included
- **Easy setup** (no cert-manager needed)
- **Free forever** for this use case

#### ⚠️ Cons:
- **Depends on Cloudflare** (single point of failure)
- **Less control** over SSL configuration
- **Requires domain** (can't use IP directly)

### Migration Steps:

#### 1. Set up Cloudflare first
- Add domain to Cloudflare
- Update nameservers
- Wait for DNS propagation (24-48 hours)

#### 2. Test HTTP still works
```bash
curl http://yourdomain.com
```

#### 3. Enable Cloudflare proxy
- Turn on orange cloud in DNS
- Test HTTPS works
```bash
curl https://yourdomain.com
```

#### 4. Update your code
- Change hardcoded URLs to HTTPS
- Update CORS settings
- Test all functionality

### Cost:
- **Free tier:** $0/month
- **Includes:** SSL, CDN, DDoS protection, DNS
- **Limits:** 100,000 requests/day (plenty for your use case)

## Option 3: Manual SSL Certificate

### Steps
1. **Generate SSL certificate** using Let's Encrypt manually
2. **Create Kubernetes secret** with the certificate
3. **Update ingress** to use the secret

## What needs to be updated

### Frontend URLs
- Update API calls from `http://64.227.134.87:30101` to `https://yourdomain.com`
- Update any hardcoded HTTP URLs

### Backend Services
- Update any internal service calls
- Update CORS settings if needed

### Ingestion Service
- Update the hardcoded URL in your signup code

## Verification

### Check certificate status
```bash
kubectl get certificates
kubectl describe certificate my-briefings-tls
```

### Test HTTPS
```bash
curl -I https://yourdomain.com
```

## Troubleshooting

### Common issues
1. **DNS not propagated** - Wait for DNS propagation
2. **Certificate not issued** - Check cert-manager logs
3. **Ingress not working** - Check ingress status

### Debug commands
```bash
kubectl get ingress
kubectl describe ingress my-briefings-ingress
kubectl logs -n cert-manager -l app=cert-manager
```

## Recommended Approach

**Option 1 (Traefik + Let's Encrypt)** - If you want full control:
- ✅ Automatic SSL certificates
- ✅ Built into k3s
- ✅ Free and reliable
- ✅ Minimal configuration

**Option 2 (Cloudflare)** - If you want simplicity and performance:
- ✅ Zero certificate management
- ✅ Better performance (CDN)
- ✅ DDoS protection
- ✅ Free forever
- ✅ Easier setup 