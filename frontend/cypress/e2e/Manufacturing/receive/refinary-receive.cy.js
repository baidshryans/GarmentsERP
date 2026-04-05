describe(' Add Refinary Receive Component', () => {
  it('should render the refinary receive form', () => {
    cy.visit("manufacturing/receive/refinary/add",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });
   cy.wait(3000);
   cy.get('input[name="form.ldgr_name"]').type('R.B.Bhosale');
   cy.wait(5000);

   cy.get('input[name="form.issue_slip_no"]').type('REF/REC/asfa/23232/00003')
   cy.get('input[name="form.issue_slip_no"]').realPress('Tab')

});
});  