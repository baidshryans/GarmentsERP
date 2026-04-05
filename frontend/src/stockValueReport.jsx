import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";

import {
    Table,
    TableRow,
    TableCell,
    TableBody,
    TableHead,
} from "@/components/ui/table";
import { fetchStockValuationReport } from "@/services/apiService";


const  StockValueReport = () => {

    const [stockData, setStockData] = useState([]);
  
    useEffect(() => {
      getStockValuationReport();
    }, []);
  
    const getStockValuationReport = async () => {
      try {
        const response = await fetchStockValuationReport(); // Adjust the API endpoint as needed
        const data = response.data;
        setStockData(data);
      } catch (error) {
        console.error('Error fetching stock valuation report:', error);
      }
    }
  
   const data = {
    stock_valuation: [
      {
        barcode: "ABC123456",
        order: 101,  // Assuming it's linked to an order
        pcs: 2,
        gw: 15.5,  // Gross weight
        nw: 14.2,  // Net weight
        purity: "22K",
        stones: [
          {
            code: 501,
            sub: 301,  // Packet ID
            pcs: 3,
            weight: 1.2,
            rate: 5000,
            value: 6000
          },
          {
            code: 502,
            sub: 302,
            pcs: 2,
            weight: 0.8,
            rate: 4500,
            value: 3600
          }
        ],
        others: [
          {
            code: 201,
            sub: null,
            pcs: 1,
            weight: 5.5,
            rate: 3000,
            value: 16500
          }
        ],
        making: 2500,
        total_value: 28600
      },
      {
        barcode: "XYZ789012",
        order: null,  // No linked order
        pcs: 1,
        gw: 10.0,
        nw: 9.5,
        purity: "18K",
        stones: [],
        others: [
          {
            code: 202,
            sub: 303,
            pcs: 1,
            weight: 4.2,
            rate: 3200,
            value: 13440
          }
        ],
        making: 2000,
        total_value: 15440
      }
    ]
  };

  
  return (
    <div className="container mt-5">
    <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm">
     

     <Table className="w-full table-fixed border-collapse">

              <TableBody>
                <TableRow className=" w-full bg-gray-100">
                  <TableCell className="w-32 px-4 py-2 "></TableCell>
                  <TableCell className="w-20 px-4 py-2 "></TableCell>
                  <TableCell className="w-20 px-4 py-2 "></TableCell>
                  <TableCell className="w-20 px-4 py-2 "></TableCell>
                  <TableCell className="w-20 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 ">Stone</TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 ">Other</TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-16 px-4 py-2 "></TableCell>
                  <TableCell className="w-32 px-4 py-2 "></TableCell>
                  <TableCell className="w-32 px-4 py-2 "></TableCell>
                </TableRow>
        
                <TableRow className=" w-full bg-gray-100">
                  <TableCell className="w-32 px-4 py-2 border">Barcode</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">Order</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">Pcs</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">Gw</TableCell>
                  <TableCell className="w-20 px-4 py-2 border">Nw</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Code</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Sub</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Pcs</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Weight</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Rate</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Value</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Item</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Pcs</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Weight</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Rate</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">Value</TableCell>
                  <TableCell className="w-32 px-4 py-2 border">Making</TableCell>
                  <TableCell className="w-32 px-4 py-2 border">Value</TableCell>
                </TableRow>
    
              
    
    
    
             

        {data.stock_valuation.map((item, index) => (
          <>
          {/* Main row */}
          <TableRow key={`main-${index}`}>
            <TableCell className="w-32 px-4 py-2 border">{item.barcode}</TableCell>
            <TableCell className="w-20 px-4 py-2 border">{item.order}</TableCell>
            <TableCell className="w-20 px-4 py-2 border">{item.pcs}</TableCell>
            <TableCell className="w-20 px-4 py-2 border">{item.gw}</TableCell>
            <TableCell className="w-20 px-4 py-2 border">{item.nw}</TableCell>
            {/* First stone entry */}
            {item.stones[0] ? (
            <>
              <TableCell className="w-16 px-4 py-2 border">{item.stones[0].code}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.stones[0].sub}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.stones[0].pcs}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.stones[0].weight}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.stones[0].rate}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.stones[0].value}</TableCell>
            </>
            ) : (
            <>{/* Empty stone cells */}
              {[...Array(6)].map((_, i) => (
              <TableCell key={i} className="w-16 px-4 py-2 border"></TableCell>
              ))}
            </>
            )}
            {/* First other entry */}
            {item.others[0] ? (
            <>
              <TableCell className="w-16 px-4 py-2 border">{item.others[0].code}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.others[0].pcs}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.others[0].weight}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.others[0].rate}</TableCell>
              <TableCell className="w-16 px-4 py-2 border">{item.others[0].value}</TableCell>
            </>
            ) : (
            <>{/* Empty other cells */}
              {[...Array(5)].map((_, i) => (
              <TableCell key={i} className="w-16 px-4 py-2 border"></TableCell>
              ))}
            </>
            )}
            <TableCell className="w-32 px-4 py-2 border">{item.making}</TableCell>
            <TableCell className="w-32 px-4 py-2 border">{item.total_value}</TableCell>
          </TableRow>

          {/* Additional stone rows */}
          {item.stones.slice(1).map((stone, stoneIndex) => (
            <TableRow key={`stone-${index}-${stoneIndex}`}>
            {/* Empty cells for non-stone columns */}
            {[...Array(5)].map((_, i) => (
              <TableCell key={i} className="w-16 px-4 py-2 border"></TableCell>
            ))}
            <TableCell className="w-16 px-4 py-2 border">{stone.code}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{stone.sub}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{stone.pcs}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{stone.weight}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{stone.rate}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{stone.value}</TableCell>
            {/* Empty cells for remaining columns */}
            {[...Array(7)].map((_, i) => (
              <TableCell key={i} className="w-16 px-4 py-2 border"></TableCell>
            ))}
            </TableRow>
          ))}

          {/* Additional other rows */}
          {item.others.slice(1).map((other, otherIndex) => (
            <TableRow key={`other-${index}-${otherIndex}`}>
            {/* Empty cells for non-other columns */}
            {[...Array(11)].map((_, i) => (
              <TableCell key={i} className="w-16 px-4 py-2 border"></TableCell>
            ))}
            <TableCell className="w-16 px-4 py-2 border">{other.code}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{other.pcs}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{other.weight}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{other.rate}</TableCell>
            <TableCell className="w-16 px-4 py-2 border">{other.value}</TableCell>
            {/* Empty cells for remaining columns */}
            {[...Array(2)].map((_, i) => (
              <TableCell key={i} className="w-16 px-4 py-2 border"></TableCell>
            ))}
            </TableRow>
          ))}
          </>
        ))}
        </TableBody>
      </Table>
      </form>
    </div>
    )}


    export default StockValueReport;
