import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { SessionProvider, useSession } from "./auth/SessionProvider";
import { ThemeProvider } from "./theme/ThemeProvider";
import { SignIn } from "./components/SignIn/SignIn";
import { PassportView } from "./components/PassportView/PassportView";
import { AuthCallback } from "./components/AuthCallback/AuthCallback";

/** Sign-in route: if already authenticated, skip straight to the passport. */
function SignInRoute() {
  const { session, loading } = useSession();
  if (loading) return null;
  if (session) return <Navigate to="/home" replace />;
  return <SignIn />;
}

export function App() {
  return (
    <ThemeProvider>
      <SessionProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<SignInRoute />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="/home" element={<PassportView />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </SessionProvider>
    </ThemeProvider>
  );
}
