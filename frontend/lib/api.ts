import { createClient } from "./supabase";
import type { ApiError } from "@/types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiClientError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

/**
 * Universal API client for communicating with the FastAPI backend.
 * Enforces JWT authentication, manages query params, and normalizes errors.
 */
export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const supabase = createClient();
  const { data: sessionData } = await supabase.auth.getSession();
  const token = sessionData.session?.access_token;

  let url: URL;
  if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
    url = new URL(endpoint);
  } else {
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    url = new URL(`${API_BASE_URL}${cleanEndpoint}`);
  }

  if (options.params) {
    Object.entries(options.params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      ...options,
      headers,
    });
  } catch (networkErr: unknown) {
    const errorMsg =
      networkErr instanceof Error
        ? `Network connection error: ${networkErr.message}`
        : "Failed to connect to API server. Please check your network connection.";
    throw new ApiClientError(errorMsg, 0, "NETWORK_ERROR");
  }

  if (!response.ok) {
    let errorMessage = `HTTP error ${response.status}`;
    let errorCode: string | undefined;

    try {
      const errorJson = (await response.json()) as ApiError;
      if (errorJson.detail) {
        errorMessage = typeof errorJson.detail === "string" 
          ? errorJson.detail 
          : JSON.stringify(errorJson.detail);
      }
      errorCode = errorJson.error_code;
    } catch {
      // Fallback to status text if response is non-JSON
      errorMessage = response.statusText || errorMessage;
    }

    throw new ApiClientError(errorMessage, response.status, errorCode);
  }

  return response.json() as Promise<T>;
}

// Convenience REST helpers
export const api = {
  get: <T>(endpoint: string, params?: RequestOptions["params"], options?: Omit<RequestOptions, "params">) =>
    apiClient<T>(endpoint, { ...options, method: "GET", params }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    apiClient<T>(endpoint, {
      ...options,
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    apiClient<T>(endpoint, {
      ...options,
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    apiClient<T>(endpoint, { ...options, method: "DELETE" }),
};
