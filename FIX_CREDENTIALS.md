# Fix GitHub Credentials Issue

You're getting a permission error because Git is using your personal account credentials. Here's how to fix it:

## Solution 1: Clear Windows Credential Manager (Recommended)

1. **Open Windows Credential Manager**:
   - Press `Win + R`
   - Type: `control /name Microsoft.CredentialManager`
   - Press Enter

2. **Go to "Windows Credentials"** tab

3. **Find and delete** any entries for:
   - `git:https://github.com`
   - `github.com`

4. **Click "Remove"** for each GitHub credential

## Solution 2: Use Personal Access Token

Since you want to use the `fcragendaldh-star` account:

1. **Generate a Personal Access Token**:
   - Go to GitHub: [github.com/settings/tokens](https://github.com/settings/tokens)
   - Sign in as `fcragendaldh-star`
   - Click "Generate new token (classic)"
   - Name: "FCR Dashboard Deployment"
   - Select scopes: `repo` (all repo permissions)
   - Click "Generate token"
   - **Copy the token** (you won't see it again!)

2. **Update remote URL to include username**:
   ```powershell
   git remote set-url origin https://fcragendaldh-star@github.com/fcragendaldh-star/fcr-dashboard.git
   ```

3. **Push** (when prompted, use the token as password):
   ```powershell
   git push -u origin main
   ```
   - Username: `fcragendaldh-star`
   - Password: `YOUR_PERSONAL_ACCESS_TOKEN`

## Solution 3: Use SSH (Alternative)

If you prefer SSH:

1. **Generate SSH key** (if you don't have one):
   ```powershell
   ssh-keygen -t ed25519 -C "fcragendaldh-star@github.com"
   ```

2. **Add SSH key to GitHub**:
   - Copy the public key: `cat ~/.ssh/id_ed25519.pub`
   - GitHub → Settings → SSH and GPG keys → New SSH key

3. **Change remote to SSH**:
   ```powershell
   git remote set-url origin git@github.com:fcragendaldh-star/fcr-dashboard.git
   ```

4. **Push**:
   ```powershell
   git push -u origin main
   ```

## Quick Fix (Easiest)

Run these commands:

```powershell
# Clear credential cache
cmdkey /delete:git:https://github.com

# Update remote URL with username
git remote set-url origin https://fcragendaldh-star@github.com/fcragendaldh-star/fcr-dashboard.git

# Push (will prompt for credentials)
git push -u origin main
```

When prompted:
- Username: `fcragendaldh-star`
- Password: Use a Personal Access Token (not your GitHub password)

## Generate Personal Access Token

1. Sign in to GitHub as `fcragendaldh-star`
2. Go to: https://github.com/settings/tokens/new
3. Name: "FCR Dashboard"
4. Select: `repo` scope
5. Generate and copy the token
6. Use it as password when pushing

---

**After fixing credentials, you should be able to push successfully!**

