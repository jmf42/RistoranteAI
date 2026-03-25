"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

import { apiFetch } from "@/lib/api";
import {
  Restaurant,
  RestaurantSummary,
  SessionResponse,
  SessionUser
} from "@/lib/types";

interface WorkspaceContextValue {
  user: SessionUser | null;
  loading: boolean;
  restaurant: Restaurant | null;
  restaurants: RestaurantSummary[];
  activeRestaurantId: string | null;
  error: string | null;
  refreshWorkspace: () => Promise<void>;
  setActiveRestaurantId: (value: string) => void;
  logout: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);
const ACTIVE_RESTAURANT_KEY = "ristorante-active-restaurant";

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null);
  const [restaurants, setRestaurants] = useState<RestaurantSummary[]>([]);
  const [activeRestaurantId, setActiveRestaurantIdState] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    try {
      const session = await apiFetch<SessionResponse>("/api/auth/me");
      setUser(session.user);
      setError(null);

      if (session.user.role === "operator") {
        const restaurantList = await apiFetch<RestaurantSummary[]>("/api/restaurants");
        setRestaurants(restaurantList);
        const stored = window.localStorage.getItem(ACTIVE_RESTAURANT_KEY);
        const fallbackId = restaurantList[0]?.id ?? null;
        const nextId =
          stored && restaurantList.some((item) => item.id === stored)
            ? stored
            : fallbackId;

        setActiveRestaurantIdState(nextId);
        if (nextId) {
          const current = await apiFetch<Restaurant>(
            `/api/restaurants/current?restaurant_id=${encodeURIComponent(nextId)}`
          );
          setRestaurant(current);
          window.localStorage.setItem(ACTIVE_RESTAURANT_KEY, nextId);
        } else {
          setRestaurant(null);
        }
      } else {
        const current = await apiFetch<Restaurant>("/api/restaurants/current");
        setRestaurants([]);
        setRestaurant(current);
        setActiveRestaurantIdState(current.id);
      }
    } catch {
      setUser(null);
      setRestaurant(null);
      setRestaurants([]);
      setActiveRestaurantIdState(null);
      setError("Sessione non disponibile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const updateActiveRestaurant = useCallback(
    async (nextId: string) => {
      setActiveRestaurantIdState(nextId);
      window.localStorage.setItem(ACTIVE_RESTAURANT_KEY, nextId);
      try {
        const current = await apiFetch<Restaurant>(
          `/api/restaurants/current?restaurant_id=${encodeURIComponent(nextId)}`
        );
        setRestaurant(current);
        setError(null);
      } catch {
        setError("Impossibile caricare il ristorante selezionato.");
      }
    },
    []
  );

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      user,
      loading,
      restaurant,
      restaurants,
      activeRestaurantId,
      error,
      refreshWorkspace: loadWorkspace,
      setActiveRestaurantId: (nextId: string) => {
        void updateActiveRestaurant(nextId);
      },
      logout: async () => {
        try {
          await apiFetch("/api/auth/logout", { method: "POST" });
        } finally {
          setUser(null);
          setRestaurant(null);
          setRestaurants([]);
          setActiveRestaurantIdState(null);
          window.localStorage.removeItem(ACTIVE_RESTAURANT_KEY);
        }
      }
    }),
    [activeRestaurantId, error, loadWorkspace, loading, restaurant, restaurants, updateActiveRestaurant, user]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace must be used inside WorkspaceProvider");
  }
  return context;
}
