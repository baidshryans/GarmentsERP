describe('RawPurchase Voucher Component', () => {
  it('should render the raw purchase Voucher form', () => {
    cy.visit("/purchase/rawpurchasevoucher/list/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });

   // Bill Details //

    cy.wait(2500);
    cy.get('[data-testid="voucher-type"]').click(); 
    cy.get('[role="option"]')  
      .contains('Vendor')      
      .click();

    cy.get('input[name="form.ldgr_name"]').type('A. Agarwal');
    cy.wait(5000);

    cy.get('[data-testid="hsn-select"]').click();
    cy.get('[role="option"]').contains('711319').click();
  

    cy.get('input[name="form.ref_no"]').type('76576');

    

    // cy.get('[data-testid="place-of-supply"]').click(); 
    // cy.get('[role="option"]').contains('Rajasthan').click();

    // cy.get('input[list="customer_order_list"]').type('C2324/00007',{ force: true });

    cy.get('input[list="serial_no_list"]').type('1');
    cy.wait(1000);


  // item details //

  
    cy.get('input[name="details.packet"]').type('DR0007');

    // cy.get('input[name="details.sub_item"]').type('GNS');

    cy.get('input[name="details.sub_pcs"]').type('2');

    cy.get('input[name="details.sub_ct"]').type('0.02');

    cy.get('input[name="details.sub_gw"]').type('0.01');

    cy.get('[data-testid="select-purity"]').click();
    cy.get('[role="option"]').contains('24').click();

    cy.get('input[name="details.loss"]').type('0.1');

    cy.get('input[name="details.tunch"]').type('0.02');

    cy.get('input[name="details.fine_wt"]').type('0.01');

    cy.get('input[name="details.rate"]').type('0.06');

    cy.get('input[name="details.value"]').type('0.00');
    cy.wait(500);
    cy.get('input[name="details.value"]').realPress('Tab');

    cy.get('input[name="form.narration"]').type("gga");


    // 3.  Bill summary//

    cy.get('input[name="form.hallmark_charge"]').type('1');

    cy.get('input[name="form.freight_amt"]').type('1');

    cy.get('input[name="form.add_chrg_amt1"]').type('0');

    cy.get('input[name="form.add_chrg_amt2"]').type('0');

    cy.get('input[name="form.discount_amt"]').type('0');

    cy.get('input[name="form.round_off "]').type('0');

    cy.get('button[type="submit"]').click();
    cy.wait(1000);

    cy.visit("purchase/rawpurchasevoucher/list/");


  });
});    