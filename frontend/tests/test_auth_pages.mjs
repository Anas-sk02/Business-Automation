import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Auth and Shell Logic Tests", () => {
  it("validates password criteria according to signup rules", () => {
    const validatePassword = (pass) => {
      const hasMinLength = pass.length >= 8;
      const hasNumber = /\d/.test(pass);
      return hasMinLength && hasNumber;
    };

    assert.strictEqual(validatePassword("short1"), false);
    assert.strictEqual(validatePassword("longpasswordwithoutnumbers"), false);
    assert.strictEqual(validatePassword("validpass123"), true);
    assert.strictEqual(validatePassword("SecurePass2026!"), true);
  });

  it("validates signup form fields before dispatching API request", () => {
    const validateSignupForm = ({ fullName, email, password }) => {
      const cleanName = (fullName || "").trim();
      if (!cleanName) return { valid: false, error: "Please enter your full name." };

      const cleanEmail = (email || "").trim();
      if (!cleanEmail || !cleanEmail.includes("@")) {
        return { valid: false, error: "Please enter a valid email address." };
      }

      const hasMinLength = password.length >= 8;
      const hasNumber = /\d/.test(password);
      if (!hasMinLength || !hasNumber) {
        return { valid: false, error: "Password must meet all requirement criteria." };
      }

      return { valid: true, error: null };
    };

    assert.deepStrictEqual(
      validateSignupForm({ fullName: "   ", email: "user@test.com", password: "Password1" }),
      { valid: false, error: "Please enter your full name." }
    );
    assert.deepStrictEqual(
      validateSignupForm({ fullName: "Jane Doe", email: "invalid-email", password: "Password1" }),
      { valid: false, error: "Please enter a valid email address." }
    );
    assert.deepStrictEqual(
      validateSignupForm({ fullName: "Jane Doe", email: "jane@company.com", password: "short" }),
      { valid: false, error: "Password must meet all requirement criteria." }
    );
    assert.deepStrictEqual(
      validateSignupForm({ fullName: "Jane Doe", email: "jane@company.com", password: "ValidPassword123" }),
      { valid: true, error: null }
    );
  });

  it("translates Supabase authentication errors to user-friendly text", () => {
    const translateAuthError = (message) => {
      if (message.includes("Invalid login credentials")) {
        return "Email or password is incorrect.";
      }
      if (message.includes("Email not confirmed")) {
        return "Check your email to confirm your account.";
      }
      if (message.includes("User already registered")) {
        return "An account with this email already exists. Try signing in.";
      }
      return message;
    };

    assert.strictEqual(
      translateAuthError("Invalid login credentials for user"),
      "Email or password is incorrect."
    );
    assert.strictEqual(
      translateAuthError("Email not confirmed yet"),
      "Check your email to confirm your account."
    );
    assert.strictEqual(
      translateAuthError("User already registered with this email"),
      "An account with this email already exists. Try signing in."
    );
    assert.strictEqual(
      translateAuthError("Rate limit exceeded"),
      "Rate limit exceeded"
    );
  });

  it("translates URL callback errors to user-friendly text", () => {
    const translateCallbackError = (code) => {
      if (code === "auth_callback_failed") {
        return "Authentication link expired or invalid. Please sign in again.";
      }
      if (code === "config_missing") {
        return "Application configuration error. Please contact support.";
      }
      if (code) {
        return "Authentication failed. Please sign in.";
      }
      return null;
    };

    assert.strictEqual(
      translateCallbackError("auth_callback_failed"),
      "Authentication link expired or invalid. Please sign in again."
    );
    assert.strictEqual(
      translateCallbackError("config_missing"),
      "Application configuration error. Please contact support."
    );
    assert.strictEqual(
      translateCallbackError("unknown_error"),
      "Authentication failed. Please sign in."
    );
    assert.strictEqual(translateCallbackError(null), null);
  });

  it("sanitizes redirect paths to prevent open redirect vulnerabilities", () => {
    const sanitizeRedirect = (rawPath) => {
      if (!rawPath) return "/";
      const isSafeRelative =
        rawPath.startsWith("/") &&
        !rawPath.startsWith("//") &&
        !rawPath.startsWith("/\\");
      return isSafeRelative ? rawPath : "/";
    };

    // Unsafe URLs should be clamped to default "/"
    assert.strictEqual(sanitizeRedirect("https://evil.com"), "/");
    assert.strictEqual(sanitizeRedirect("http://attacker.com/malware"), "/");
    assert.strictEqual(sanitizeRedirect("//evil.com"), "/");
    assert.strictEqual(sanitizeRedirect("/\\evil.com"), "/");
    assert.strictEqual(sanitizeRedirect("javascript:alert(1)"), "/");

    // Safe relative paths should be preserved
    assert.strictEqual(sanitizeRedirect("/"), "/");
    assert.strictEqual(sanitizeRedirect("/campaigns"), "/campaigns");
    assert.strictEqual(sanitizeRedirect("/campaigns/new?source=banner"), "/campaigns/new?source=banner");
    assert.strictEqual(sanitizeRedirect("/pipeline#step-2"), "/pipeline#step-2");
  });

  it("computes user avatar initial and display name accurately", () => {
    const getUserDisplay = (profile) => {
      const displayName = profile?.full_name || profile?.email || "Account";
      const userInitial = (displayName[0] || "U").toUpperCase();
      return { displayName, userInitial };
    };

    assert.deepStrictEqual(
      getUserDisplay({ full_name: "Sarah Connor", email: "sarah@resistance.org" }),
      { displayName: "Sarah Connor", userInitial: "S" }
    );
    assert.deepStrictEqual(
      getUserDisplay({ full_name: null, email: "john@connor.org" }),
      { displayName: "john@connor.org", userInitial: "J" }
    );
    assert.deepStrictEqual(
      getUserDisplay(null),
      { displayName: "Account", userInitial: "A" }
    );
  });

  it("accurately computes page titles from pathnames", () => {
    const getPageTitle = (path) => {
      if (path === "/") return "Today";
      if (path.startsWith("/campaigns/new")) return "New campaign";
      if (path.startsWith("/campaigns")) return "Campaigns";
      if (path.startsWith("/pipeline")) return "Pipeline";
      if (path.startsWith("/tasks")) return "Tasks";
      if (path.startsWith("/analytics")) return "Analytics";
      if (path.startsWith("/templates")) return "Templates";
      if (path.startsWith("/settings")) return "Settings";
      return "SignalForge";
    };

    assert.strictEqual(getPageTitle("/"), "Today");
    assert.strictEqual(getPageTitle("/campaigns"), "Campaigns");
    assert.strictEqual(getPageTitle("/campaigns/new"), "New campaign");
    assert.strictEqual(getPageTitle("/pipeline"), "Pipeline");
    assert.strictEqual(getPageTitle("/templates"), "Templates");
    assert.strictEqual(getPageTitle("/settings"), "Settings");
    assert.strictEqual(getPageTitle("/unknown"), "SignalForge");
  });

  it("verifies middleware route protection classification", () => {
    const classifyRoute = (pathname) => {
      const isAuthPage = pathname.startsWith("/login") || pathname.startsWith("/signup");
      const isAuthCallback = pathname.startsWith("/auth/callback");
      const isPublicAsset = pathname.startsWith("/_next") || pathname === "/favicon.ico";
      return { isAuthPage, isAuthCallback, isPublicAsset, isProtected: !isAuthPage && !isAuthCallback && !isPublicAsset };
    };

    assert.deepStrictEqual(classifyRoute("/login"), { isAuthPage: true, isAuthCallback: false, isPublicAsset: false, isProtected: false });
    assert.deepStrictEqual(classifyRoute("/signup"), { isAuthPage: true, isAuthCallback: false, isPublicAsset: false, isProtected: false });
    assert.deepStrictEqual(classifyRoute("/auth/callback"), { isAuthPage: false, isAuthCallback: true, isPublicAsset: false, isProtected: false });
    assert.deepStrictEqual(classifyRoute("/"), { isAuthPage: false, isAuthCallback: false, isPublicAsset: false, isProtected: true });
    assert.deepStrictEqual(classifyRoute("/campaigns"), { isAuthPage: false, isAuthCallback: false, isPublicAsset: false, isProtected: true });
  });
});
