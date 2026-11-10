import { Navigate } from "react-router-dom";
import { useEffect, useState } from "react";
import api from "@/api/api";
import ProtectedRoute from "@/routes/ProtectedRoute";

function AdminRoute({ children }) {
    const [isAdmin, setIsAdmin] = useState(null);

    useEffect(() => {
        api.get("/auth/profile/")
            .then(res => {
                if (res.data.role === "admin") {
                    setIsAdmin(true);
                } else {
                    setIsAdmin(false);
                }
            })
            .catch(() => {
                setIsAdmin(false);
            }
            );
    }, []);

    if (isAdmin === null) {
        return <div>checking...</div>
    }

    if (isAdmin === true) {
        return (
            <ProtectedRoute>
                {children}
            </ProtectedRoute>
        );
    } else {
        return <Navigate to="/login" />;
    }
}

export default AdminRoute;