/**
 * lilyApp Module is the entry point for Lily related Angular code
 */
var lilyApp = angular.module('lilyApp', [
    'ui.router',
    'ngResource',
    'ngSanitize',
    'ncy-angular-breadcrumb',

    // Controllers
    'lilyControllers',
    'ContactsControllers',
    'dashboardControllers',

    // global modules
    'lilyDirectives',
    'lilyFilters',
    'lilyServices'
]);

lilyApp.config([
    '$urlRouterProvider',
    '$resourceProvider',
    '$breadcrumbProvider',

    function(
        $urlRouterProvider,
        $resourceProvider,
        $breadcrumbProvider
    ){
        // Don't strip trailing slashes from calculated URLs, because django needs them
        $resourceProvider.defaults.stripTrailingSlashes = false;
        $urlRouterProvider.otherwise('/');
        $breadcrumbProvider.setOptions({
            templateUrl: 'breadcrumbs.html'
        });
    }
]);
