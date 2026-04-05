// src/pages/NotFoundPage.jsx
import { Button } from "@/components/ui/button"; // Adjust the import path based on your setup
import { useNavigate } from "react-router-dom";

const NotFoundPage = () => {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center h-screen text-center space-y-4">
      <h1 className="text-4xl font-bold">404 - Page Not Found</h1>
      <p className="text-lg text-muted-foreground">
        Sorry, we couldn’t find the page you were looking for.
      </p>
      <Button onClick={() => navigate("/")} variant="outline">
        Go Back to Home
      </Button>
    </div>
  );
};

export default NotFoundPage;
