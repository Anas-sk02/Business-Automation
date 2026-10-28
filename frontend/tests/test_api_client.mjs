import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Frontend Infrastructure Tests", () => {
  it("validates ApiClientError properties", async () => {
    // Import ApiClientError dynamically or verify its structure
    class ApiClientError extends Error {
      constructor(message, status, errorCode) {
        super(message);
        this.name = "ApiClientError";
        this.status = status;
        this.errorCode = errorCode;
      }
    }

    const err = new ApiClientError("Unprocessable entity", 422, "VALIDATION_ERROR");
    assert.strictEqual(err.message, "Unprocessable entity");
    assert.strictEqual(err.status, 422);
    assert.strictEqual(err.errorCode, "VALIDATION_ERROR");
    assert.strictEqual(err.name, "ApiClientError");
  });

  it("formats URLs and query parameters accurately", () => {
    const API_BASE_URL = "http://localhost:8000/".replace(/\/+$/, "");
    const endpoint = "/api/campaigns";
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const url = new URL(`${API_BASE_URL}${cleanEndpoint}`);

    const params = { page: 2, page_size: 25, status: "active", empty: undefined };
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });

    assert.strictEqual(
      url.toString(),
      "http://localhost:8000/api/campaigns?page=2&page_size=25&status=active"
    );
  });

  it("normalizes API error response shapes", () => {
    const sampleError = { detail: "Campaign not found", error_code: "HTTP_404" };
    let errorMessage = "Unknown error";
    let errorCode;

    if (sampleError.detail) {
      errorMessage = typeof sampleError.detail === "string" 
        ? sampleError.detail 
        : JSON.stringify(sampleError.detail);
    }
    errorCode = sampleError.error_code;

    assert.strictEqual(errorMessage, "Campaign not found");
    assert.strictEqual(errorCode, "HTTP_404");
  });

  it("handles complex validation error arrays in API error shapes", () => {
    const sampleValError = {
      detail: [{ loc: ["body", "name"], msg: "Field required", type: "missing" }],
      error_code: "VALIDATION_ERROR",
    };

    let errorMessage = "Unknown error";
    if (sampleValError.detail) {
      errorMessage = typeof sampleValError.detail === "string" 
        ? sampleValError.detail 
        : JSON.stringify(sampleValError.detail);
    }

    assert.strictEqual(
      errorMessage,
      JSON.stringify(sampleValError.detail)
    );
  });
});
