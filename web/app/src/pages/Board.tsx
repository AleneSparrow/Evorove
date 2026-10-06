import { Navigate } from "react-router-dom";

/** The watch board lives on /app. This route stays so old People links still open it. */
export default function Board() {
  return <Navigate to="/app" replace />;
}
