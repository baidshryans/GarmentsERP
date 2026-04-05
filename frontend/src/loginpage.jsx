import { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import { getRetails, getStates } from "@/services/apiService";
import { FieldContainer } from "@/Utils";

const RetailSelection = () => {
  const { control, watch, setValue } = useForm();
  const [statesData, setstatesData] = useState([]);

  useEffect(() => {
    async function fetchData() {
      const [states] = await Promise.all([
        getRetails()
      ]);
      if (states.success) setstatesData(states.data.results[0].location);
    }
    fetchData();
  }, []);

  const retail = watch('retail')

  useEffect(() => {
    // Set initial retail from localStorage
    const storedRetail = localStorage.getItem('retail_code');
    if (storedRetail && !retail) {
      setValue('retail', storedRetail);
    }
  }, [control]);

  useEffect(() => {
    if (retail) {
      const selectedRetail = statesData.find(state => state.retail_code === retail);
      if (selectedRetail) {
        const currentStoredRetail = localStorage.getItem('retail_code');
        if (currentStoredRetail !== selectedRetail.retail_code) {
          localStorage.setItem('retail_code', selectedRetail.retail_code);
          console.log(selectedRetail)
          localStorage.setItem('state_code', selectedRetail.retail.state.code);
          window.location.reload();
        }
      }
    }
  }, [retail, statesData]);

  return (

    <div className="flex items-center justify-between max-w-72 px-4 h-14">

      <Label htmlFor="place_of_supply" className="text-nowrap">Retail</Label>
      <Controller
        name="retail"
        control={control}
        render={({ field }) => (
          <Select onValueChange={field.onChange} value={field.value}>
            <SelectTrigger >
              <SelectValue placeholder="" />
            </SelectTrigger>

            <SelectContent>
              {statesData.map((sp, index) => (
                <SelectItem key={index} value={`${sp.retail_code}`}>{sp.retail_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
    </div>

  );
};

export default RetailSelection;
