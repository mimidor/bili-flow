import { shallowRef } from "vue";

import { api } from "./api";

export type AuthRole = {
  id: number;
  code: string;
  name: string;
};

export type AuthUser = {
  authenticated: boolean;
  id: number;
  username: string;
  display_name?: string | null;
  is_super_admin: boolean;
  roles: AuthRole[];
  permissions: string[];
  menu_keys: string[];
  token?: string | null;
};

const AUTH_TOKEN_KEY = "auth_token";
export const currentUserState = shallowRef<AuthUser | null | undefined>(undefined);

let cachedUser: AuthUser | null | undefined;
let pendingUserRequest: Promise<AuthUser | null> | null = null;

export async function fetchCurrentUser(force = false): Promise<AuthUser | null> {
  if (!force && cachedUser !== undefined) {
    return cachedUser;
  }
  if (!pendingUserRequest) {
    pendingUserRequest = api
      .get<AuthUser>("/auth/me")
      .then((data) => {
        cachedUser = data;
        currentUserState.value = data;
        return data;
      })
      .catch(() => {
        cachedUser = null;
        currentUserState.value = null;
        return null;
      })
      .finally(() => {
        pendingUserRequest = null;
      });
  }
  return pendingUserRequest;
}

export async function login(username: string, password: string): Promise<AuthUser> {
  const user = await api.post<AuthUser>("/auth/login", { username, password });
  if (user.token) {
    localStorage.setItem(AUTH_TOKEN_KEY, user.token);
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  }
  cachedUser = user;
  currentUserState.value = user;
  return user;
}

export async function logout(): Promise<void> {
  try {
    await api.post("/auth/logout", {});
  } finally {
    cachedUser = null;
    currentUserState.value = null;
    localStorage.removeItem(AUTH_TOKEN_KEY);
  }
}

export function clearAuthCache(): void {
  cachedUser = undefined;
  pendingUserRequest = null;
  currentUserState.value = undefined;
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

export function hasMenuAccess(user: AuthUser | null | undefined, menuKey?: string | null): boolean {
  if (!menuKey) return true;
  if (!user) return false;
  if (user.is_super_admin) return true;
  return user.menu_keys.includes(menuKey);
}
