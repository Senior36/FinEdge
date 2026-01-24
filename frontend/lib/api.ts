import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type { SentimentalAnalysisRequest, SentimentalAnalysisResponse } from '@/types';
import { getAuthStore } from '@/stores/authStore';

/**
 * API Client Configuration
 * Handles all HTTP requests to the backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api`,
  timeout: 30000, // 30 seconds timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request Interceptor
 * Adds JWT token to all requests
 */
apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthStore().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response Interceptor
 * Handles common error responses
 */
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError) => {
    if (error.response) {
      const status = error.response.status;
      
      // Handle 401 Unauthorized
      if (status === 401) {
        const authStore = getAuthStore();
        authStore.logout();
        window.location.href = '/login';
      }
      
      // Handle 429 Rate Limit
      if (status === 429) {
        return Promise.reject({
          message: 'Too many requests. Please try again later.',
          code: 'RATE_LIMIT_EXCEEDED',
        });
      }
      
      // Handle 500 Server Error
      if (status >= 500) {
        return Promise.reject({
          message: 'Server error. Please try again later.',
          code: 'SERVER_ERROR',
        });
      }
    }
    
    // Handle network errors
    if (error.code === 'ECONNABORTED') {
      return Promise.reject({
        message: 'Request timeout. Please try again.',
        code: 'TIMEOUT',
      });
    }
    
    if (error.code === 'ERR_NETWORK') {
      return Promise.reject({
        message: 'Network error. Please check your connection.',
        code: 'NETWORK_ERROR',
      });
    }
    
    return Promise.reject(error);
  }
);

/**
 * API Error Handler
 * Converts API errors to user-friendly messages
 */
export const handleApiError = (error: any): string => {
  if (error.response?.data?.detail) {
    return error.response.data.detail;
  }
  
  if (error.message) {
    return error.message;
  }
  
  return 'An unexpected error occurred. Please try again.';
};

/**
 * Sentiment Analysis API
 */
export const sentimentApi = {
  /**
   * Analyze sentiment for a ticker
   */
  analyze: async (
    request: SentimentalAnalysisRequest,
    config?: InternalAxiosRequestConfig
  ): Promise<SentimentalAnalysisResponse> => {
    const response = await apiClient.post<SentimentalAnalysisResponse>(
      '/analyze/sentimental',
      request,
      config
    );
    return response.data;
  },
  
  /**
   * Get analysis history
   */
  getHistory: async (config?: InternalAxiosRequestConfig): Promise<any[]> => {
    const response = await apiClient.get<any[]>('/user/history', config);
    return response.data;
  },
  
  /**
   * Delete analysis from history
   */
  deleteHistoryItem: async (
    id: string,
    config?: InternalAxiosRequestConfig
  ): Promise<void> => {
    await apiClient.delete(`/user/history/${id}`, config);
  },
};

/**
 * Authentication API
 */
export const authApi = {
  /**
   * Login user
   */
  login: async (
    email: string,
    password: string,
    config?: InternalAxiosRequestConfig
  ): Promise<{ token: string; user: any }> => {
    const response = await apiClient.post<{ token: string; user: any }>(
      '/auth/login',
      { email, password },
      config
    );
    return response.data;
  },
  
  /**
   * Register user
   */
  register: async (
    email: string,
    password: string,
    full_name?: string,
    config?: InternalAxiosRequestConfig
  ): Promise<{ token: string; user: any }> => {
    const response = await apiClient.post<{ token: string; user: any }>(
      '/auth/register',
      { email, password, full_name },
      config
    );
    return response.data;
  },
  
  /**
   * Logout user
   */
  logout: async (config?: InternalAxiosRequestConfig): Promise<void> => {
    await apiClient.post('/auth/logout', {}, config);
  },
  
  /**
   * Get user profile
   */
  getProfile: async (config?: InternalAxiosRequestConfig): Promise<any> => {
    const response = await apiClient.get<any>('/user/profile', config);
    return response.data;
  },
  
  /**
   * Update user profile
   */
  updateProfile: async (
    data: { full_name?: string; email?: string },
    config?: InternalAxiosRequestConfig
  ): Promise<any> => {
    const response = await apiClient.put<any>('/user/profile', data, config);
    return response.data;
  },
  
  /**
   * Change password
   */
  changePassword: async (
    current_password: string,
    new_password: string,
    config?: InternalAxiosRequestConfig
  ): Promise<void> => {
    await apiClient.put(
      '/user/change-password',
      { current_password, new_password },
      config
    );
  },
};

/**
 * Health Check API
 */
export const healthApi = {
  /**
   * Check API health
   */
  check: async (config?: InternalAxiosRequestConfig): Promise<any> => {
    const response = await apiClient.get<any>('/health', config);
    return response.data;
  },
};

export default apiClient;
