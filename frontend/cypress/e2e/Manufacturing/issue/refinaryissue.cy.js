
/// working. but ldgr some time throw error///

describe(' Add Refinary Issue Component', () => {
  it('should render the refinary issue form', () => {
    cy.visit("manufacturing/issue/refinary/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });



cy.wait(3000);

cy.get('input[name="form.ldgr_name"]').type('A.Figuciredo');
cy.wait(1000);
cy.get('input[name="table.packet"]').type('DR0006');

cy.get('input[name="table.item"]').type('GPS');

cy.get('[data-id="select-purity"]').click();
cy.get('[role="option"]').contains('18').click();

cy.get('input[name="table.description"]').type('gg');

cy.get('input[name="table.pcs"]').type('5');

cy.get('input[name="table.ct"]').type('3');

cy.get('input[name="table.gw"]').type('4');
cy.get('input[name="table.gw"]').realPress();

cy.get('button[type="submit"]').click();
cy.wait(2000);

cy.visit('manufacturing/issue/refinary/');

  });
});        