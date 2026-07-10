"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

interface UserIdContextValue {
  userId: string;
  setUserId: (id: string) => void;
}

const UserIdContext = createContext<UserIdContextValue>({
  userId: "",
  setUserId: () => undefined,
});

const STORAGE_KEY = "health-platform-user-id";

export function UserIdProvider({ children }: { children: ReactNode }) {
  const [userId, setUserIdState] = useState<string>("");

  useEffect(() => {
    setUserIdState(window.localStorage.getItem(STORAGE_KEY) ?? "");
  }, []);

  const setUserId = (id: string) => {
    setUserIdState(id);
    window.localStorage.setItem(STORAGE_KEY, id);
  };

  return (
    <UserIdContext.Provider value={{ userId, setUserId }}>
      {children}
    </UserIdContext.Provider>
  );
}

export function useUserId(): UserIdContextValue {
  return useContext(UserIdContext);
}
