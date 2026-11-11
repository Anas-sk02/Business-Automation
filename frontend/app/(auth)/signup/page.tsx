"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, Loader2, Check, X, Mail } from "lucide-react";

export default function SignupPage() {
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isConfirmedStep, setIsConfirmedStep] = useState(false);
  const [resendStatus, setResendStatus] = useState<string | null>(null);

  const supabase = createClient();

  // Password criteria check
  const hasMinLength = password.length >= 8;
  const hasNumber = /\d/.test(password);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const cleanName = fullName.trim();
    if (!cleanName) {
      setErrorMsg("Please enter your full name.");
      return;
    }

    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes("@")) {
      setErrorMsg("Please enter a valid email address.");
      return;
    }

    if (!hasMinLength || !hasNumber) {
      setErrorMsg("Password must meet all requirement criteria.");
      return;
    }

    setIsLoading(true);

    try {
      const origin = window.location.origin;
      const { data, error } = await supabase.auth.signUp({
        email: cleanEmail,
        password,
        options: {
          data: {
            full_name: cleanName,
          },
          emailRedirectTo: `${origin}/auth/callback`,
        },
      });

      if (error) {
        if (error.message.includes("User already registered")) {
          setErrorMsg("An account with this email already exists. Try signing in.");
        } else {
          setErrorMsg(error.message);
        }
        setIsLoading(false);
        return;
      }

      // If Supabase requires email confirmation, session will be null
      if (data?.user && !data.session) {
        setIsConfirmedStep(true);
        setIsLoading(false);
      } else {
        // Immediate login
        router.push("/");
        router.refresh();
      }
    } catch {
      setErrorMsg("An unexpected connection error occurred. Please try again.");
      setIsLoading(false);
    }
  };

  const handleResendEmail = async () => {
    setResendStatus(null);
    try {
      const { error } = await supabase.auth.resend({
        type: "signup",
        email: email.trim(),
      });
      if (error) {
        setResendStatus("Failed to resend confirmation email: " + error.message);
      } else {
        setResendStatus("Confirmation email resent successfully.");
      }
    } catch {
      setResendStatus("Failed to resend email. Please try again later.");
    }
  };


  if (isConfirmedStep) {
    return (
      <div className="min-h-screen flex flex-col justify-center items-center p-4 bg-background">
        <div className="w-full max-w-[400px] space-y-6 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-petrol-soft flex items-center justify-center text-primary">
            <Mail className="h-6 w-6" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              Check your email
            </h1>
            <p className="text-sm text-muted-foreground">
              We sent a verification link to{" "}
              <span className="font-medium text-foreground">{email}</span>. Click the link to complete your signup.
            </p>
          </div>

          {resendStatus && (
            <p className="text-xs text-muted-foreground">{resendStatus}</p>
          )}

          <div className="space-y-3">
            <Button
              variant="outline"
              className="w-full"
              onClick={handleResendEmail}
            >
              Resend email
            </Button>
            <Link href="/login" className="block text-sm text-primary hover:underline">
              Return to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col justify-center items-center p-4 bg-background">
      <div className="w-full max-w-[400px] space-y-6">
        <div className="space-y-1 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            SignalForge
          </h1>
          <p className="text-sm text-muted-foreground">
            Create an account to start your work queue
          </p>
        </div>

        {errorMsg && (
          <div className="p-3 text-sm rounded-md bg-problem-soft text-problem border border-problem/30">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSignup} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="fullName">Full name</Label>
            <Input
              id="fullName"
              type="text"
              placeholder="First and last name"
              autoComplete="name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="email">Email address</Label>
            <Input
              id="email"
              type="email"
              placeholder="name@company.com"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Create password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                tabIndex={-1}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>

            {/* Password requirements indicators */}
            {password.length > 0 && (
              <div className="pt-2 space-y-1 text-xs">
                <div className={`flex items-center gap-1.5 ${hasMinLength ? "text-good" : "text-muted-foreground"}`}>
                  {hasMinLength ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                  <span>At least 8 characters</span>
                </div>
                <div className={`flex items-center gap-1.5 ${hasNumber ? "text-good" : "text-muted-foreground"}`}>
                  {hasNumber ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                  <span>At least 1 number</span>
                </div>
              </div>
            )}
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={isLoading || !hasMinLength || !hasNumber}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating account...
              </>
            ) : (
              "Create account"
            )}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link
            href="/login"
            className="text-primary hover:underline font-medium"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
