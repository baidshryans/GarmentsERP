describe('Barcode Management List Component', () => {
  it('should render the barcode management list form', () => {
    cy.visit('inventory/barcodemanagement/list/add/',{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });


  cy.get('input[name="form.voucher_no"]').type('PV/asfa/23232/00010');

  cy.get('input[name="form.design_code"]').type('010');

  cy.get('input[name="form.kr_code"]').type('47095');

  cy.get('input[name="form.huid"]').type('0010');

  cy.get('input[name="form.order_no"]').type('C2324/00010');

  cy.get('input[name="form.making_val"]').type('2');

  cy.get('[ className="making-type"]').click();
  cy.get('[role="option"]').contains('% of wt').click();

  cy.get('input[name="form.other_chg"]').type('20');




  });
});
  
