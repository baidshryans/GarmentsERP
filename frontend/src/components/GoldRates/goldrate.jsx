import React, { useState, useEffect } from "react";
import apiClient from "../../services/apiClient";
import { fetchPurity } from "../../services/apiService";
import { useForm } from "react-hook-form";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Skeleton } from "@/components/ui/skeleton";
import { Loader2 } from "lucide-react";
import { useGoldRates } from "../../contexts/GoldRateContext";

const GoldRateForm = () => {
  const [purityList, setPurityList] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();
  const { refreshGoldRates } = useGoldRates();

  const form = useForm({
    defaultValues: {
      rates: {}
    }
  });

  useEffect(() => {
    setIsLoading(true);
    fetchPurity()
      .then((res) => {
        const results = res.data.data?.results || res.data || [];
        setPurityList(results);
        
        // Initialize the form with empty rates
        const initialRates = {};
        results.forEach(p => {
          initialRates[p.id] = "";
        });
        
        form.reset({ rates: initialRates });
      })
      .catch((err) => {
        console.error("Error fetching purities", err);
        toast({
          title: "Error",
          description: "Failed to load purity options. Please try again.",
          variant: "destructive"
        });
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [form, toast]);

  const onSubmit = (data) => {
    // Convert the form data structure to the API expected format
    const formattedData = Object.entries(data.rates)
      .filter(([_, v]) => (v?.buying_rate ?? "") !== "" || (v?.selling_rate ?? "") !== "")
      .map(([purityId, v]) => ({
        purity: purityId,
        buying_rate: v.buying_rate || null,
        selling_rate: v.selling_rate || null,
        rate: v.selling_rate || v.buying_rate || 0,
      }));
    
    if (formattedData.length === 0) {
      toast({
        title: "Warning",
        description: "Please enter at least one gold rate",
        variant: "warning"
      });
      return;
    }
    
    setIsLoading(true);
    apiClient.post("/goldrates/api/gold-rate-create/", formattedData)
      .then(() => {
        toast({
          title: "Success",
          description: "Gold rates added successfully",
          variant: "success"
        });
        refreshGoldRates();
        form.reset({ rates: {} });
      })
      .catch((err) => {
        console.error("Error submitting form", err);
        toast({
          title: "Error",
          description: "Failed to submit gold rates. Please try again.",
          variant: "destructive"
        });
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useF4Submit(form.handleSubmit(onSubmit));

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader>
        <CardTitle className="text-2xl font-bold">Gold Rate Management</CardTitle>
        <CardDescription>Enter the current rates for different gold purities</CardDescription>
      </CardHeader>
      
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            {isLoading ? (
              <>
                <div className="space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-10 w-full" />
                </div>
                <div className="space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-10 w-full" />
                </div>
                <div className="space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-10 w-full" />
                </div>
              </>
            ) : purityList.length > 0 ? (
              purityList.map((p) => (
                <div key={p.id} className="space-y-2">
                  <Label className="font-semibold">{p.purity} Karat</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <FormField
                      control={form.control}
                      name={`rates.${p.id}.buying_rate`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs">Buying</FormLabel>
                          <FormControl>
                            <Input type="number" placeholder="Buy rate" step="0.01" {...field} />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name={`rates.${p.id}.selling_rate`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-xs">Selling</FormLabel>
                          <FormControl>
                            <Input type="number" placeholder="Sell rate" step="0.01" {...field} />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center p-4 text-muted-foreground">
                No purity options available. Please add gold purity types first.
              </div>
            )}
          </CardContent>
          
          <CardFooter>
            <Button 
              type="submit" 
              className="w-full" 
              disabled={isLoading || purityList.length === 0}
            >
              {isLoading && <Loader2 className="mr-2 size-4 animate-spin" />}
              {isLoading ? "Processing..." : "Save Gold Rates"}
            </Button>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
};

export default GoldRateForm;