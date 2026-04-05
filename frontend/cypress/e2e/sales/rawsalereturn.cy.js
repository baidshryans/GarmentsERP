describe('RawSales Return Component', () => {
  it('should render the rawsales return form', () => {
    cy.visit('/sales/rawsalesreturn/add/', {
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b');
        window.localStorage.setItem('retail_code', 'asfa');
      },
    });


  cy.wait(2500);
  
  cy.get('input[name="billno"]').type('SV/asfa/23232/00001')
  cy.get('input[name="billno"]').realPress('Tab');

  cy.wait(2000);



   /// bill details///
   

  //  cy.get('input[name="form.discount"]').type('0.002');

  //  cy.get('input[name="form.cgst_amt"]').type('0.001');

  //  cy.get('input[name="form.sgst_amt"]').type('0.001');

  //  cy.get('button[type="submit"]').click();
 });
});        