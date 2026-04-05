// cypress are working. but karigar name sometime not null(error)

describe(' Add karigar issue Component', () => {
  it('should render the karigar issue form', () => {
    cy.visit("manufacturing/issue/jobwork/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });

   

   cy.get('[data-id="slip-type"]').click();
   cy.get('[role="option"]').contains('Customer Order').click();
   cy.wait(2000);

   cy.get('input[name="form.karigar_ldgr_name"]').type('A.Gupta');

  
   /// order item-details///

   cy.get('input[name="table.design_code"]').type('03');

   cy.get('input[name="table.item"]').type('GNS');

   cy.get('[data-id="purity"]').click();
   cy.get('[role="option"]').contains('24').click();

   cy.get('input[name="table.pcs"]').type('2');

   cy.get('input[name="table.approx_wt"]').type('10');

   cy.get('input[name="table.size"]').type('5');

   cy.get('input[name="table.due_date"]').type('2025-07-20');

   cy.get('input[name="table.remarks"]').type('gg');
   cy.get('input[name="table.remarks"]').realPress('Tab');

   cy.wait(2500);
   cy.get('button[type="submit"]').click();


   cy.visit('manufacturing/issue/jobwork/');

  });
});    