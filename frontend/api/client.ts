import axios from "axios";

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Shared axios instance. All API modules should import this instead of
 * creating their own instances. Base URL and default headers are set here.
 */
const apiClient = axios.create({
  baseURL: apiUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

export default apiClient;
