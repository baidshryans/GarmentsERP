 /// working. but some time ledger can be throw error ////


describe('Sale Voucher Component', () => {
  it('should render the sale Voucher form', () => {
    cy.visit("sales/salesvoucher/list/add",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });
 


 cy.get('input[name="form.gst_billno"]').type('873453');
 cy.wait(2000);

 cy.get('input[name="form.ldgr_name"]').type('A.Gupta');
 
 cy.get('[data-testid="sales-person1"]').click();
 cy.wait(1000);
 cy.get('[role="option"]').contains('Jane Smith').click();

cy.get('[data-testid="sales-person2"]').click();
cy.get('[role="option"]').contains('Emily Davis').click();

// cy.get('[data-testid="place-of-supply"]').click(); 
// cy.get('[role="option"]').contains('Rajasthan').click();

cy.get('input[name="form.remarks"]').type('ok');

cy.get('input[name="form.mode_of_transport"]').type('ffd');

cy.get('[data-testid="hsn-select"]').click();
cy.get('[role="option"]').contains('711319').click();

cy.get('input[name="barcode"]').type('9719135787656');

cy.get('input[name="barcode"]').realPress('Tab');
cy.wait(500);

cy.get('input[name="form.cash"]').type('2000');


/// payments details ////


cy.get('input[name="bank.amount"]').type('100');

cy.get('input[name="bank.chq_no"]').type('12345');

cy.get('input[name="bank.bank_name"]').type('CASH');

cy.get('input[name="bank.jij_bank"]').type('adq');

cy.get('input[name="bank.chq_date"]').type('2025-08-22');

cy.get('[data-testid="btn"]').click();

/// Bill summary///


cy.get('input[name="form.freight_charge"]').type('1');

// cy.get('input[name="form.mrp"]').type('1');

 cy.get('input[name="form.other_charge"]').type('1');

 cy.get('input[name="form.discount"]').type('0');

 cy.get('input[name="form.round_off"]').type('0.01');

//  cy.get('button[type="submit"]').click();

//  cy.get('button[type="submit"]').contains('Save').click();

//  cy.visit("sales/salesvoucher/list/");

  


  });
});