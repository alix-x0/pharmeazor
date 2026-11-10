import { Navigate } from "react-router-dom";
import { useEffect, useState } from "react";
import api from "@/api/api";
import ProtectedRoute from "@/routes/ProtectedRoute";

function PharmacistRoute({ children }) {
    const [isPharmacist, setIsPharmacist] = useState(null);

    useEffect(() => {
        api.get("/auth/profile/")
            .then(res => {
                // Check for both 'PHARMACIST' and 'pharmacist' to be safe
                const role = res.data.role?.toLowerCase();
                if (role === "pharmacist" || role === "admin") {
                    setIsPharmacist(true);
                } else {
                    setIsPharmacist(false);
                }
            })
            .catch(() => {
                setIsPharmacist(false);
            });
    }, []);

    if (isPharmacist === null) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    if (isPharmacist === true) {
        return (
            <ProtectedRoute>
                {children}
            </ProtectedRoute>
        );
    } else {
        return <Navigate to="/" />;
    }
}

export default PharmacistRoute;
