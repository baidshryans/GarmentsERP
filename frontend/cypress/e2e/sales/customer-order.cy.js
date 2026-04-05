 /// working///


describe('Customer Order Component', () => {
  it('should render the customer order form', () => {
    cy.visit('sales/customerorder/list/add/', {
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b');
        window.localStorage.setItem('retail_code', 'asfa');
      },
    });

  cy.wait(3000);
  cy.get('input[name="form.gold_rate_date"]').type('2025-06-24');
  cy.wait(1500);

  cy.get('input[name="form.ldgr_code_name"]').type('A.Das');


 cy.get('[data-id="saleperson-1"]').click();
 cy.get('[role="option"]').contains('Jane Smith').click();

 cy.get('[data-id="saleperson-2"]').click();
 cy.get('[role="option"]').contains('John Doe').click();

 cy.get('input[name="form.advance_amt"]').type('10');

 cy.get('input[name="form.est_amount"]').type('10');

 cy.get('input[name="form.delivery_date"]').type('2025-06-27');


 cy.get('[data-id="select-sales"]').click();
 cy.get('[role="option"]').contains('New Booking').click();

 cy.get('input[name="form.status"]').type('gg');

 /// item details///

 cy.get('input[name="table.item_id"]').type('DMS');

 cy.get('[data-id="pty"]').click();
 cy.get('[role="option"]').contains('999').click();

 cy.get('input[name="table.pcs"]').type('2');

 cy.get('input[name="table.gw"]').type('2');

 cy.get('input[name="table.making_amt"]').type('10');

 cy.get('[data-id="making"]').click();
 cy.get('[role="option"]').contains('% of wt').click();

 cy.get('input[name="table.other_chg"]').type('2');

 cy.get('input[name="table.size"]').type('1');

 cy.get('input[name="table.remarks"]').type('gg');

 cy.get('input[name="table.remarks"]').realPress('Tab');

 cy.get('button[type="submit"]').click();


 cy.visit('sales/customerorder/list/');



  });
});