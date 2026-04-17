import React from "react";
import { CircleAlert, PenSquare } from "lucide-react";
import { Link } from "react-router-dom";
import { useGoldRates } from "./contexts/GoldRateContext";

const GoldRates = () => {
  const { goldRates, loading, error } = useGoldRates();

  // Sort rates by purity for consistent display
  const sortedRates = [...goldRates].sort((a, b) => a.purity - b.purity);

  if (loading) {
    return <div className="text-sm text-gray-500">Loading gold rates...</div>;
  }

  if (error) {
    return (
      <div className="flex items-center text-sm text-red-500">
        <CircleAlert className="size-4 mr-1" />
        <span>Could not load gold rates</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between w-full">
      <div className="flex items-center space-x-4 text-sm">
        <span className="font-medium">Gold Rates:</span>
        <div className="flex space-x-3">
          {sortedRates.map((rate) => (
            <div key={rate.purity} className="flex items-center">
              <span className="font-medium">{rate.purity_name}K:</span>
              <span className="ml-1">₹{rate.rate.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>

      <Link
        to="/goldrate/form"
        className="flex items-center text-sm font-medium text-primary hover:text-primary transition-colors"
      >
        <PenSquare className="size-4 mr-1" />
        Update Rates
      </Link>
    </div>
  );
};

export default GoldRates;
