/// <reference types="vite/client" />

/**
 * API Configuration
 */
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Helper to build full API URLs
 */
export function getApiPath(path: string): string {
    // Remove leading slash if present
    const normalizedPath = path.startsWith('/') ? path.slice(1) : path;

    // If the path already starts with 'api/', use it as is
    if (normalizedPath.startsWith('api/')) {
        return `${API_BASE_URL}/${normalizedPath}`;
    }

    // Otherwise prepend 'api/'
    return `${API_BASE_URL}/api/${normalizedPath}`;
}

/**
 * API Endpoints
 */
export const API = {
    HEALTH: getApiPath('health'),
    SEARCH: getApiPath('search'),
} as const;