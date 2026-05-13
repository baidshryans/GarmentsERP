// src/pages/NotFoundPage.jsx
import { Button } from "@/components/ui/button"; // Adjust the import path based on your setup
import { useNavigate } from "react-router-dom";

const ForbiddenPage = () => {
    const navigate = useNavigate();

    return (
        <div className="flex flex-col items-center justify-center h-screen text-center space-y-4">
            <h1 className="text-4xl font-bold">403 - Forbidden</h1>
            <p className="text-lg text-muted-foreground">
                Sorry, you don�t have permission to access this page.
            </p>
            <Button onClick={() => navigate("/")} variant="outline">
                Go Back to Home
            </Button>
        </div>
    );
};

export default ForbiddenPage;
