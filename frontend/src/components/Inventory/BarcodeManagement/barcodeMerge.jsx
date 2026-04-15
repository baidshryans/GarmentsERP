import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { fetchMainItem, fetchReceiveSlipNo, fetchKarigarIssues, fetchPurity, getLedgers, createCustomerOrder, getStates, fetchNextBarcode, fetchBarcodeList, mergeBarcode } from "@/services/apiService";
import { Link } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { SquarePen, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { renderErrorTree } from "../../../Utils";

const MergeBarcode = () => {
    const { toast } = useToast()
    const { register, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
        defaultValues: {
            rate_18kt: 0,
            rate_22kt: 0,
            rate_24kt: 0,
            advance_amt
                :
                0,
            est_amount
                :
                0,
            date1: new Date().toISOString().split("T")[0],
            fix_gold_rate: false,
            salesman_1: null
        },
    });
    const navigate=useNavigate();
    const [rs, setRows] = useState([]);
    const [salespersonData, setSalespersonData] = useState([]);
    const [mainItemData, setMainItemData] = useState([]);
    const [customers, setCustomers] = useState([]);
    const [purityData, setPurityData] = useState([]);
    const [barcodes, setBarcodes] = useState([]);
    useEffect(() => {
        async function fetchData() {
            const [customers,barcodeList, barcode, mainItem, purity] = await Promise.all([
                getLedgers(),
                fetchBarcodeList(),
                fetchNextBarcode(),
                fetchMainItem(),
                fetchPurity(),
            ]);
            if (customers.success) setCustomers(customers.data.results);
            if (barcodeList.success) setBarcodes(barcodeList.data.results);
            if (barcode.success) setValue("table.barcode", barcode.data.barcode);
            if (mainItem.success) setMainItemData(mainItem.data.results ?? mainItem.data);
            if (purity.success) setPurityData(purity.data.results ?? purity.data);
        }
        fetchData();
    }, []);

    const evaluateFormula = (formula, data) => {
        try {
            // Handle nested SUM operations first
            let processedFormula = formula.replace(/SUM\(([^)]+)\)/g, (match, path) => {
                const parts = path.trim().split('.');
                let array = data[parts[0]];
                if (!Array.isArray(array)) return 0;
                const sum = array.reduce((acc, item) => {
                    return parseFloat(acc) + parseFloat(item[parts[1]]);
                }, 0);
                return sum;
            });

            processedFormula = processedFormula.replace(/(\b[A-Za-z_][A-Za-z0-9_]*\b)|('[^']*')|(\d+)/g, (match, variable, quoted, number) => {
                if (quoted) return quoted; // Preserve anything inside single quotes
                if (number) return number; // Preserve numbers as they are

                if (data.hasOwnProperty(variable)) {
                    let value = data[variable];
                    return typeof value === "number" ? `(${value})` : `'${value}'`;
                }

                return "0"; // Default replacement if variable is not found
            });




            // Evaluate the final expression
            return new Function(`return ${processedFormula};`)()?.toFixed(2);
        } catch (error) {
            console.error("Formula evaluation error:", error);
            return "";
        }
    };

    const main_formulas = {
        pcs: 'SUM(rs.pcs)',
        gw: 'SUM(rs.gw)',
        nw: 'SUM(rs.nw)',
        making_val: 'SUM(rs.making_val)',
        total_amount: 'SUM(rs.total_amount)',
    }

    useEffect(() => {
        const form = { ...getValues('form'), rs: rs };
        Object.keys(main_formulas).forEach((col) => {
            setValue(`form.${col}`, evaluateFormula(main_formulas[col], form));
        })

    }, [rs]);

    const onSubmit = (data) => {
        const sub_data = getValues('form')
        sub_data.barcodedetails_set = rs.reduce((acc, curr) => {
            if (curr.barcodedetails_set && Array.isArray(curr.barcodedetails_set)) {
                return [...acc, ...curr.barcodedetails_set];
            }
            return acc;
        }, []);

        sub_data.barcodedetails_set = sub_data.barcodedetails_set.map(item => {
            const { id, ...rest } = item;
            return rest;
        });

        mergeBarcode(sub_data)
            .then((response) => {
                if (response.success) {
                    toast({
                        title: "Form submitted successfully!",
                    });  // Success toast
                    setTimeout(() => {
                        navigate("");
                    }, 2000);
                } else if (response.status < 500) {
                    toast({
                        title: "Form submission failed. Please try again.",
                        description: renderErrorTree(response.error),
                    });  // Error toast
                } else {
                    toast({ title: "An error occurred. Please try again later." });
                }
            })
            .catch((error) => {
                console.error("Error submitting form:", error);
                toast({ title: "An error occurred. Please try again later." });  // Error toast on catch
            });
    };

    useF4Submit(handleSubmit(onSubmit));

    const handleEdit = (index) => {
        const row = rs[index];
        reset(row);
        setRows((prev) => prev.filter((_, i) => i !== index));
    };

    const handleDelete = (index) => {
        setRows((prev) => prev.filter((_, i) => i !== index));
    };

    const fix_gold_rate = watch("fix_gold_rate")

    const handleKeyDown = (e) => {
        if (e.key === "Tab") {
            const rowVals = getValues("@/table")
            setRows([...rs, rowVals])

        }
    };


    const handleKeyDownBarcode = (e) => {
        if (e.key === "Tab") {
            const barcode = getValues("form.old_barcode")
            const foundBarcode = barcodes.find(item => item.barcode === barcode);
            if (foundBarcode) {
                setRows([...rs, { ...foundBarcode }])
                // Object.keys(foundBarcode).forEach(key => {
                //     setValue(`table.${key}`, foundBarcode[key]);
                // });
            }
        }
    };

    return (
        <div className="container mt-5">
            <form
                className="p-4 shadow-lg rounded-lg bg-white"
                id="orderForm"
                onSubmit={handleSubmit(onSubmit)}
            >

                <hr className="my-3" />
                <br></br>

                {/* Date, Order No, Fixed Gold Rate */}
                <div className="grid grid-cols-4 gap-4 mb-4">
                    <FieldContainer>
                        <Label htmlFor="barcode" className="text-nowrap">Enter Old/Currenet Barcode</Label>
                        <Input list="barcode_list" onKeyDown={handleKeyDownBarcode} type="text" {...register("form.old_barcode")} />
                        <datalist id="barcode_list" >
                            {barcodes.map((barcode, index) => (
                                <option key={index} value={barcode.barcode}>{barcode.barcode}</option>

                            ))}

                        </datalist>
                    </FieldContainer>
                </div>
                <div className="grid grid-cols-4 gap-4 mb-4">
                    <FieldContainer>
                        <Label htmlFor="new_barcode" className="text-nowrap">New Barcode</Label>
                        <Input type="text" {...register("form.barcode")} />
                    </FieldContainer>
                    <FieldContainer>
                        <Label htmlFor="design_no" className="text-nowrap">Design No</Label>
                        <Input type="text" {...register("form.design_code")} />
                    </FieldContainer>
                    <FieldContainer>
                        <Label htmlFor="gold_loss_wt" className="text-nowrap">Gold Loss Wt</Label>
                        <Input type="number" {...register("form.loss_rate")} />
                    </FieldContainer>
                    <FieldContainer>
                        <Label htmlFor="loss_value" className="text-nowrap">Gold Loss Value</Label>
                        <Input type="number" {...register("form.loss_rate")} />
                    </FieldContainer>
                </div>

                <div className="grid grid-cols-4 gap-4 mb-4">
                    <FieldContainer>

                    </FieldContainer>
                    <FieldContainer>
                        <Label htmlFor="status" className="text-nowrap">Order No</Label>
                        <Input type="text" {...register("form.customer_order")} />
                    </FieldContainer>
                    <FieldContainer>
                        <Label htmlFor="status" className="text-nowrap">Karigar Code</Label>
                        <Input list="party_list"
                            onChange={(e) => {
                                const selectedCustomer = customers.find(
                                    (customer) => customer.ac_name === e.target.value
                                );
                                selectedCustomer ? setValue("kr_code", selectedCustomer.id) : e.target.value;

                            }} required />
                        <Input type="hidden" {...register("kr_code")} />
                        <datalist id="party_list" >
                            {customers.map((customer, index) => (
                                <option key={index} value={customer.ac_name}>{customer.mobile1}</option>

                            ))}

                        </datalist>
                    </FieldContainer>
                </div>

                <hr className="my-3" />
                <br></br>

                {/* Stone Details*/}
                <Table className="w-full table-fixed border-collapse">
                    <TableBody>

                        <h6 className="w-28 px-4 py-2 ">Main Item</h6>
                        <TableRow className=" w-full bg-gray-100">
                            <TableCell className="w-28 px-4 py-2 border">Item</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Description</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Purity</TableCell>

                            <TableCell className="w-28 px-4 py-2 border">Pcs</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Gw</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Nw</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Making</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Making Type</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Other Charge</TableCell>
                            <TableCell className="w-28 px-4 py-2 border">Total</TableCell>


                        </TableRow>
                        {rs.map((row, index) => (
                            <TableRow key={index} className="w-full bg-white">
                                <TableCell className="w-28 px-4 py-2 border">
                                    <Button
                                        variant="secondary"
                                        size="sm"
                                        onClick={() => handleEdit(index)}
                                    >
                                        <SquarePen className="mr-1" />
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleDelete(index)}
                                    >
                                        <Trash2 className="mr-1" />
                                    </Button>
                                    {row.item}

                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">
                                    {row.item_name}
                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">

                                    {row.purity}

                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">

                                    {row.pcs}

                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">

                                    {row.gw != null ? parseFloat(row.gw).toFixed(3) : "—"}

                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">

                                    {row.nw != null ? parseFloat(row.nw).toFixed(3) : "—"}

                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">

                                    {row.making_val}

                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">

                                    {row.making_type}

                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">
                                    {row.other_chg}

                                </TableCell>
                                <TableCell className="w-28 px-4 py-2 border">

                                    {row.total_amount}

                                </TableCell>


                            </TableRow>
                        ))}

                        <TableRow>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input list="item_list" {...register("form.item")} />
                                <datalist id="item_list">
                                    {mainItemData.map((item, index) => (
                                        <option key={index} value={item.short_code}  > {item.item_name}</option>
                                    ))}

                                </datalist>
                            </TableCell>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input type="text" readOnly value={""} disabled />
                            </TableCell>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input {...register("form.purity")} />
                            </TableCell>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input type="number" {...register("form.pcs")} />
                            </TableCell>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input type="number" {...register("form.gw")} />
                            </TableCell>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input type="number" {...register("form.nw")} />
                            </TableCell>

                            <TableCell className="w-28 px-4 py-2 border">
                                <Input type="text" {...register("form.making_val")} />
                            </TableCell>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input
                                    {...register("form.making_type")}
                                />
                            </TableCell>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input type="text" {...register("form.other_chg")} />
                            </TableCell>
                            <TableCell className="w-28 px-4 py-2 border">
                                <Input onKeyDown={(e) => handleKeyDown(e)} type="number" {...register("form.total_amount")} />
                            </TableCell>
                        </TableRow>




                    </TableBody>
                </Table>



                {/* Submit */}
                <div className="flex justify-center mt-5">
                    <Button type="submit" className="mr-4">
                        Save
                    </Button>
                    <Button variant="outline">Cancel</Button>
                </div>
            </form>
        </div>
    );
};

export default MergeBarcode;
