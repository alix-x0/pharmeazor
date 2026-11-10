// Axios instance + our 2 interceptors (request + response)

import axios from "axios";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "@/constants";

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api", // Fallback added to ensure requests don't fail if .env is missing/not loaded
})

// request intercepter : function that runs before every request + yjib access token mn local storage + y7otou fl header automatically

api.interceptors.request.use((config) => {
    const accessToken = localStorage.getItem(ACCESS_TOKEN);
    if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
});

// response interceptor (token refresh logic) : function that runs when a request fails + status=401(Unauthorized=token expired) +gets a refresh token from localstorage + calls backend to get a new access token

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            const refreshToken = localStorage.getItem(REFRESH_TOKEN);
            if (!refreshToken) {
                localStorage.clear();
                window.location.href = "/login";
                return Promise.reject(error);
            }

            try {
                const res = await axios.post(     // we use axios. and not api. to avoid infinite loops api keeps calling its interceptor infinitely
                    `${import.meta.env.VITE_API_URL}/auth/refresh/`,
                    { refresh: refreshToken }
                );

                localStorage.setItem(ACCESS_TOKEN, res.data.access);

                api.defaults.headers.Authorization = `Bearer ${res.data.access}`;
                return api(originalRequest);

            } catch (err) {
                localStorage.clear();
                window.location.href = "/login";
                return Promise.reject(err);
            }
        }
        return Promise.reject(error);
    }

);

export default api;